"""Scan newly released or previewed cards for supercycle candidates.

Fetches cards from the Scryfall search API that were released (or previewed)
since the last scan, asks Claude which of them plausibly belong to one of the
supercycles in ``data/manual/supercycles.yaml``, and renders the answer as a
Markdown body suitable for a GitHub issue. A small state file remembers which
cards have already been evaluated so preview cards are not re-judged every week.
"""

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Any

import anthropic
import requests
import typer
import yaml
from loguru import logger

from card_utils import is_traditional_card
from constants import REQUEST_HEADERS, REQUEST_TIMEOUT

MANUAL_DATA_FOLDER = Path("data").resolve() / "manual"
SUPERCYCLES_FILE = MANUAL_DATA_FOLDER / "supercycles.yaml"
STATE_FILE = MANUAL_DATA_FOLDER / "supercycle_scan_state.json"

SCRYFALL_SEARCH_URL = "https://api.scryfall.com/cards/search"
SCRYFALL_PAGE_DELAY_SECONDS = 0.1  # Scryfall asks for <= 10 requests/second
DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_MODEL = "claude-opus-5"
CONFIDENCE_LEVELS = ("high", "medium", "low")

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "card": {"type": "string"},
                    "cycle": {"type": "string"},
                    "confidence": {"type": "string", "enum": list(CONFIDENCE_LEVELS)},
                    "rationale": {"type": "string"},
                },
                "required": ["card", "cycle", "confidence", "rationale"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["candidates", "notes"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You are helping maintain a list of Magic: The Gathering supercycles (also called
mega-mega cycles): groups of cards that share a naming pattern, mechanical template,
or design theme but were printed across many different sets and years.

You will receive the current supercycle definitions as YAML (names, member cards,
and comments describing the pattern), a list of previously rejected candidates, and a
list of newly released or previewed cards. Decide which new cards plausibly belong to
an existing supercycle.

Rules:
- Only propose cards from the provided new-card list, using their exact names.
- Only propose existing cycle names from the YAML, spelled exactly.
- Finished cycles may still gain members if a new card clearly fits the pattern.
- Judge fit by the cycle's naming pattern, mechanical template, and the comment
  describing it. A shared word in the name is not enough on its own; a shared
  template is not enough if the cycle is defined by its name.
- Use "high" confidence only when the card is an unmistakable member. Use "low" for
  loose thematic fits, and skip anything weaker than that.
- Previously rejected candidates show the maintainer's taste. Do not re-propose
  them, and do not propose cards that fit for the same weak reason.
- If nothing fits, return an empty candidates list. An empty list is a good answer.
"""


# --------------------------------------------------------------------------- state


def default_state() -> dict[str, Any]:
    """Return an empty scan state."""
    return {"last_scan": None, "evaluated": {}, "proposed": [], "rejected": []}


def load_state(path: Path = STATE_FILE) -> dict[str, Any]:
    """Load the scan state file, returning an empty state if it does not exist."""
    if not path.exists():
        return default_state()
    with path.open("r", encoding="utf-8") as f:
        state = default_state()
        state.update(json.load(f))
        return state


def save_state(state: dict[str, Any], path: Path = STATE_FILE) -> None:
    """Write the scan state file with stable key ordering."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def prune_evaluated(state: dict[str, Any], since: date) -> None:
    """Forget evaluated cards that can no longer match a ``date>=since`` query."""
    state["evaluated"] = {
        name: released
        for name, released in state["evaluated"].items()
        if date.fromisoformat(released) >= since
    }


# ------------------------------------------------------------------------ scryfall


def fetch_new_cards(since: date, session: requests.Session | None = None) -> list[dict[str, Any]]:
    """Fetch non-reprint, non-digital cards released or previewed on or after ``since``."""
    session = session or requests.Session()
    query = f"date>={since.isoformat()} not:reprint -is:digital"
    params: dict[str, Any] = {"q": query, "unique": "cards", "order": "released", "dir": "asc"}
    url: str | None = SCRYFALL_SEARCH_URL
    cards: list[dict[str, Any]] = []

    while url:
        response = session.get(url, params=params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        if response.status_code == 404:
            # Scryfall returns 404 when a search matches nothing.
            break
        response.raise_for_status()
        payload = response.json()
        cards.extend(payload.get("data", []))
        url = payload.get("next_page") if payload.get("has_more") else None
        params = {}  # next_page URLs already carry the query string
        if url:
            time.sleep(SCRYFALL_PAGE_DELAY_SECONDS)

    logger.info("Fetched {} cards released on or after {}", len(cards), since)
    return cards


def select_cards_to_evaluate(
    cards: list[dict[str, Any]], state: dict[str, Any]
) -> list[dict[str, Any]]:
    """Drop reprints, non-traditional cards, and cards already evaluated."""
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for card in cards:
        name = card.get("name")
        if not name or name in seen or name in state["evaluated"]:
            continue
        if card.get("reprint") or not is_traditional_card(card):
            continue
        seen.add(name)
        selected.append(card)
    return selected


# ---------------------------------------------------------------------- prompting


def card_oracle_text(card: dict[str, Any]) -> str:
    """Return oracle text, joining the faces of multi-faced cards."""
    if card.get("oracle_text"):
        return card["oracle_text"]
    faces = card.get("card_faces") or []
    return " // ".join(face.get("oracle_text", "") for face in faces if face.get("oracle_text"))


def format_card(card: dict[str, Any]) -> str:
    """Render a card as a compact single-line record for the prompt."""
    oracle = " ".join(card_oracle_text(card).split())
    return (
        f"{card['name']} | {card.get('type_line', '')} | {card.get('mana_cost', '')} | "
        f"{card.get('set_name', '')} ({card.get('set', '').upper()}) | "
        f"{card.get('released_at', '')} | {oracle}"
    )


def build_user_prompt(
    supercycles_yaml: str, cards: list[dict[str, Any]], rejected: list[dict[str, Any]]
) -> str:
    """Assemble the user turn: cycle definitions, rejections, then the new cards."""
    rejected_lines = [
        f"- {entry['card']} -> {entry['cycle']}: {entry.get('reason') or 'no reason given'}"
        for entry in rejected
    ] or ["(none)"]
    card_lines = [format_card(card) for card in cards]
    return (
        "## Supercycle definitions (YAML)\n\n"
        f"```yaml\n{supercycles_yaml}\n```\n\n"
        "## Previously rejected candidates\n\n" + "\n".join(rejected_lines) + "\n\n## New cards\n\n"
        "Format: name | type line | mana cost | set | release date | oracle text\n\n"
        + "\n".join(card_lines)
    )


def judge_candidates(
    client: Any,
    supercycles_yaml: str,
    cards: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Ask Claude which new cards belong to a supercycle. Returns the parsed JSON."""
    response = client.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": build_user_prompt(supercycles_yaml, cards, rejected)}
        ],
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA},
        },
    )
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"Unexpected stop reason from model: {response.stop_reason}")
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)


def resolve_candidates(
    judgement: dict[str, Any], cards: list[dict[str, Any]], cycle_names: set[str]
) -> list[dict[str, Any]]:
    """Attach Scryfall data to each candidate; drop names the model invented."""
    by_name = {card["name"]: card for card in cards}
    resolved: list[dict[str, Any]] = []
    for candidate in judgement.get("candidates", []):
        card = by_name.get(candidate["card"])
        if card is None:
            logger.warning("Model proposed unknown card {!r}; dropping", candidate["card"])
            continue
        if candidate["cycle"] not in cycle_names:
            logger.warning(
                "Model proposed unknown cycle {!r} for {}; dropping",
                candidate["cycle"],
                card["name"],
            )
            continue
        resolved.append(
            {
                "card": card["name"],
                "cycle": candidate["cycle"],
                "confidence": candidate["confidence"],
                "rationale": candidate["rationale"],
                "scryfall_uri": card.get("scryfall_uri", ""),
                "set": card.get("set", ""),
                "set_name": card.get("set_name", ""),
                "released_at": card.get("released_at", ""),
            }
        )
    resolved.sort(key=lambda c: (c["cycle"], CONFIDENCE_LEVELS.index(c["confidence"]), c["card"]))
    return resolved


# --------------------------------------------------------------------- reporting


def render_issue_body(
    candidates: list[dict[str, Any]], since: date, evaluated_count: int, notes: str = ""
) -> str:
    """Render candidates as a Markdown issue body grouped by supercycle."""
    lines = [
        f"Scanned **{evaluated_count}** new cards released or previewed since {since.isoformat()}.",
        "",
    ]
    current_cycle = None
    for candidate in candidates:
        if candidate["cycle"] != current_cycle:
            current_cycle = candidate["cycle"]
            lines.extend([f"## {current_cycle}", ""])
        lines.append(
            f"- [ ] [{candidate['card']}]({candidate['scryfall_uri']}) "
            f"({candidate['set_name']}, {candidate['released_at']}) "
            f"— confidence: **{candidate['confidence']}**"
        )
        lines.append(f"  - {candidate['rationale']}")
    if notes:
        lines.extend(["", "## Notes from the model", "", notes])
    lines.extend(
        [
            "",
            "---",
            "To accept a candidate, add it to `data/manual/supercycles.yaml`. To reject one so it",
            "is not proposed again for the same reason, run:",
            "",
            "```",
            'uv run supercycle_scanner.py reject "Card Name" --cycle "Cycle Name" --reason "..."',
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- cli

app = typer.Typer(help="Scan new Magic cards for supercycle candidates.", no_args_is_help=True)


def load_cycle_names(supercycles_yaml: str) -> set[str]:
    """Extract the set of cycle names from the supercycles YAML text."""
    data = yaml.safe_load(supercycles_yaml)
    return {cycle["name"] for cycle in data["supercycles"]}


@app.command()
def scan(
    since: Annotated[
        str | None,
        typer.Option(help="Only consider cards released on/after this date (YYYY-MM-DD)."),
    ] = None,
    issue_file: Annotated[
        Path | None, typer.Option(help="Write the issue body here when candidates are found.")
    ] = None,
    json_file: Annotated[
        Path | None, typer.Option(help="Write the resolved candidates as JSON here.")
    ] = None,
    model: Annotated[str, typer.Option(envvar="SUPERCYCLE_SCAN_MODEL")] = DEFAULT_MODEL,
    dry_run: Annotated[
        bool, typer.Option(help="List the cards that would be evaluated; skip the API and state.")
    ] = False,
    state_file: Annotated[Path, typer.Option(hidden=True)] = STATE_FILE,
    supercycles_file: Annotated[Path, typer.Option(hidden=True)] = SUPERCYCLES_FILE,
):
    """Fetch new cards, ask Claude for supercycle candidates, and write an issue body."""
    state = load_state(state_file)
    today = date.today()
    if since:
        since_date = date.fromisoformat(since)
    elif state["last_scan"]:
        since_date = date.fromisoformat(state["last_scan"])
    else:
        since_date = today - timedelta(days=DEFAULT_LOOKBACK_DAYS)

    prune_evaluated(state, since_date)
    cards = select_cards_to_evaluate(fetch_new_cards(since_date), state)
    logger.info("{} cards to evaluate after filtering", len(cards))

    if dry_run:
        for card in cards:
            typer.echo(format_card(card))
        typer.echo(f"candidates=0 evaluated={len(cards)}")
        return

    candidates: list[dict[str, Any]] = []
    notes = ""
    if cards:
        supercycles_yaml = supercycles_file.read_text(encoding="utf-8")
        judgement = judge_candidates(
            anthropic.Anthropic(), supercycles_yaml, cards, state["rejected"], model=model
        )
        candidates = resolve_candidates(judgement, cards, load_cycle_names(supercycles_yaml))
        notes = judgement.get("notes", "")
        logger.info("Model proposed {} candidates", len(candidates))
    else:
        logger.info("No new cards to evaluate; skipping model call")

    for card in cards:
        state["evaluated"][card["name"]] = card["released_at"]
    for candidate in candidates:
        state["proposed"].append(
            {
                "card": candidate["card"],
                "cycle": candidate["cycle"],
                "proposed_on": today.isoformat(),
            }
        )
    state["last_scan"] = today.isoformat()
    save_state(state, state_file)

    if candidates and issue_file:
        issue_file.parent.mkdir(parents=True, exist_ok=True)
        issue_file.write_text(
            render_issue_body(candidates, since_date, len(cards), notes), encoding="utf-8"
        )
        logger.info("Wrote issue body to {}", issue_file)
    if json_file:
        json_file.parent.mkdir(parents=True, exist_ok=True)
        json_file.write_text(json.dumps(candidates, indent=2) + "\n", encoding="utf-8")

    typer.echo(f"candidates={len(candidates)} evaluated={len(cards)}")
    if github_output := os.environ.get("GITHUB_OUTPUT"):
        with Path(github_output).open("a", encoding="utf-8") as f:
            f.write(f"candidates={len(candidates)}\nevaluated={len(cards)}\n")


@app.command()
def reject(
    card: Annotated[str, typer.Argument(help="Exact card name.")],
    cycle: Annotated[str, typer.Option(help="Supercycle the card was proposed for.")],
    reason: Annotated[str, typer.Option(help="Why it does not fit; shown to the model.")] = "",
    state_file: Annotated[Path, typer.Option(hidden=True)] = STATE_FILE,
):
    """Record a rejected candidate so it is not proposed again."""
    state = load_state(state_file)
    if any(r["card"] == card and r["cycle"] == cycle for r in state["rejected"]):
        typer.echo(f"{card} -> {cycle} is already rejected")
        return
    state["rejected"].append({"card": card, "cycle": cycle, "reason": reason})
    save_state(state, state_file)
    typer.echo(f"Rejected {card} -> {cycle}")


if __name__ == "__main__":
    app()
