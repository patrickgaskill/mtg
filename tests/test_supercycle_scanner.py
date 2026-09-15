"""Tests for the supercycle candidate scanner."""

import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import responses
from typer.testing import CliRunner

import supercycle_scanner as scanner

SUPERCYCLES_YAML = """\
supercycles:
  - name: Infinity Stones
    finished: false # Marvel crossover stones
    cards:
      - The Soul Stone
  - name: Thirsts
    finished: false # Blue instants drawing three cards, discarding two
    cards:
      - Thirst for Knowledge
"""


def make_card(name, **overrides):
    card = {
        "name": name,
        "type_line": "Legendary Artifact — Infinity Stone",
        "mana_cost": "{1}{W}",
        "oracle_text": "Indestructible\n{T}: Add {W}.",
        "set": "msh",
        "set_name": "Marvel Super Heroes",
        "released_at": "2026-06-26",
        "reprint": False,
        "scryfall_uri": f"https://scryfall.com/card/msh/21/{name.lower().replace(' ', '-')}",
        "border_color": "black",
        "layout": "normal",
        "set_type": "expansion",
    }
    card.update(overrides)
    return card


# ----------------------------------------------------------------------- state


class TestState:
    def test_load_missing_file_returns_default(self, tmp_path):
        state = scanner.load_state(tmp_path / "missing.json")
        assert state == scanner.default_state()

    def test_round_trip(self, tmp_path):
        path = tmp_path / "state.json"
        state = scanner.default_state()
        state["last_scan"] = "2026-09-01"
        state["evaluated"]["Foo"] = "2026-09-05"
        scanner.save_state(state, path)
        assert scanner.load_state(path) == state

    def test_load_fills_missing_keys(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"last_scan": "2026-09-01"}))
        state = scanner.load_state(path)
        assert state["evaluated"] == {}
        assert state["rejected"] == []

    def test_prune_evaluated_drops_cards_before_since(self):
        state = scanner.default_state()
        state["evaluated"] = {"Old": "2026-08-01", "Preview": "2026-10-02"}
        scanner.prune_evaluated(state, date(2026, 9, 1))
        assert state["evaluated"] == {"Preview": "2026-10-02"}


# -------------------------------------------------------------------- scryfall


class TestFetchNewCards:
    @responses.activate
    def test_paginates_and_sleeps_between_pages(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr(scanner.time, "sleep", sleeps.append)
        next_url = "https://api.scryfall.com/cards/search?page=2&q=x"
        responses.add(
            responses.GET,
            scanner.SCRYFALL_SEARCH_URL,
            json={"data": [make_card("A")], "has_more": True, "next_page": next_url},
        )
        responses.add(responses.GET, next_url, json={"data": [make_card("B")], "has_more": False})

        cards = scanner.fetch_new_cards(date(2026, 9, 1))

        assert [c["name"] for c in cards] == ["A", "B"]
        assert sleeps == [scanner.SCRYFALL_PAGE_DELAY_SECONDS]
        first_url = responses.calls[0].request.url
        assert "date%3E%3D2026-09-01" in first_url
        assert "not%3Areprint" in first_url
        assert "-is%3Adigital" in first_url
        assert (
            responses.calls[0].request.headers["User-Agent"]
            == scanner.REQUEST_HEADERS["User-Agent"]
        )

    @responses.activate
    def test_no_results_returns_empty_list(self):
        responses.add(
            responses.GET,
            scanner.SCRYFALL_SEARCH_URL,
            status=404,
            json={"object": "error", "code": "not_found"},
        )
        assert scanner.fetch_new_cards(date(2026, 9, 1)) == []


class TestSelectCardsToEvaluate:
    def test_filters_reprints_non_traditional_and_evaluated(self):
        state = scanner.default_state()
        state["evaluated"]["Already Seen"] = "2026-09-05"
        cards = [
            make_card("Keep Me"),
            make_card("Keep Me"),  # duplicate printing
            make_card("Reprint", reprint=True),
            make_card("Token", layout="token"),
            make_card("Silver", border_color="silver"),
            make_card("Already Seen"),
        ]
        assert [c["name"] for c in scanner.select_cards_to_evaluate(cards, state)] == ["Keep Me"]


# ------------------------------------------------------------------- prompting


class TestPromptBuilding:
    def test_format_card_flattens_oracle_text(self):
        line = scanner.format_card(make_card("The Mind Stone"))
        assert line.startswith("The Mind Stone | Legendary Artifact — Infinity Stone | {1}{W} | ")
        assert "Marvel Super Heroes (MSH) | 2026-06-26 | Indestructible {T}: Add {W}." in line

    def test_format_card_joins_faces(self):
        card = make_card(
            "Front // Back",
            oracle_text="",
            card_faces=[{"oracle_text": "Front text"}, {"oracle_text": "Back text"}],
        )
        assert scanner.card_oracle_text(card) == "Front text // Back text"

    def test_user_prompt_includes_yaml_rejections_and_cards(self):
        rejected = [{"card": "Green Goblin, Nemesis", "cycle": "Nemeses", "reason": "epithet"}]
        prompt = scanner.build_user_prompt(
            SUPERCYCLES_YAML, [make_card("The Mind Stone")], rejected
        )
        assert "name: Infinity Stones" in prompt
        assert "- Green Goblin, Nemesis -> Nemeses: epithet" in prompt
        assert "The Mind Stone | " in prompt

    def test_user_prompt_without_rejections(self):
        prompt = scanner.build_user_prompt(SUPERCYCLES_YAML, [make_card("X")], [])
        assert "(none)" in prompt


class TestJudgeCandidates:
    def test_calls_model_with_schema_and_parses_json(self):
        payload = {
            "candidates": [
                {
                    "card": "The Mind Stone",
                    "cycle": "Infinity Stones",
                    "confidence": "high",
                    "rationale": "Second Infinity Stone.",
                }
            ],
            "notes": "",
        }
        client = MagicMock()
        client.messages.create.return_value = SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps(payload))],
        )

        result = scanner.judge_candidates(
            client, SUPERCYCLES_YAML, [make_card("The Mind Stone")], []
        )

        assert result == payload
        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["model"] == scanner.DEFAULT_MODEL
        assert kwargs["thinking"] == {"type": "adaptive"}
        assert kwargs["output_config"]["format"]["schema"] == scanner.RESPONSE_SCHEMA
        assert kwargs["system"] == scanner.SYSTEM_PROMPT

    def test_unexpected_stop_reason_raises(self):
        client = MagicMock()
        client.messages.create.return_value = SimpleNamespace(stop_reason="max_tokens", content=[])
        try:
            scanner.judge_candidates(client, SUPERCYCLES_YAML, [make_card("X")], [])
        except RuntimeError as e:
            assert "max_tokens" in str(e)
        else:
            raise AssertionError("expected RuntimeError")


class TestResolveCandidates:
    def test_attaches_scryfall_data_and_drops_unknowns(self):
        cards = [make_card("The Mind Stone"), make_card("Thirst for Identity", set="fra")]
        judgement = {
            "candidates": [
                {
                    "card": "Thirst for Identity",
                    "cycle": "Thirsts",
                    "confidence": "low",
                    "rationale": "r1",
                },
                {
                    "card": "The Mind Stone",
                    "cycle": "Infinity Stones",
                    "confidence": "high",
                    "rationale": "r2",
                },
                {
                    "card": "Made Up Card",
                    "cycle": "Thirsts",
                    "confidence": "high",
                    "rationale": "r3",
                },
                {
                    "card": "The Mind Stone",
                    "cycle": "Not A Cycle",
                    "confidence": "high",
                    "rationale": "r4",
                },
            ]
        }
        resolved = scanner.resolve_candidates(judgement, cards, {"Infinity Stones", "Thirsts"})
        assert [(c["card"], c["cycle"]) for c in resolved] == [
            ("The Mind Stone", "Infinity Stones"),
            ("Thirst for Identity", "Thirsts"),
        ]
        assert resolved[0]["scryfall_uri"] == "https://scryfall.com/card/msh/21/the-mind-stone"
        assert resolved[0]["set_name"] == "Marvel Super Heroes"

    def test_sorts_by_cycle_then_confidence(self):
        cards = [make_card("A"), make_card("B"), make_card("C")]
        judgement = {
            "candidates": [
                {"card": "A", "cycle": "Z", "confidence": "low", "rationale": ""},
                {"card": "B", "cycle": "Z", "confidence": "high", "rationale": ""},
                {"card": "C", "cycle": "A", "confidence": "medium", "rationale": ""},
            ]
        }
        resolved = scanner.resolve_candidates(judgement, cards, {"A", "Z"})
        assert [c["card"] for c in resolved] == ["C", "B", "A"]


# ------------------------------------------------------------------- reporting


class TestRenderIssueBody:
    def test_groups_by_cycle_with_scryfall_links(self):
        candidates = [
            {
                "card": "The Mind Stone",
                "cycle": "Infinity Stones",
                "confidence": "high",
                "rationale": "Second stone.",
                "scryfall_uri": "https://scryfall.com/card/msh/21/the-mind-stone",
                "set": "msh",
                "set_name": "Marvel Super Heroes",
                "released_at": "2026-06-26",
            },
            {
                "card": "Thirst for Identity",
                "cycle": "Thirsts",
                "confidence": "low",
                "rationale": "Draws three.",
                "scryfall_uri": "https://scryfall.com/card/fra/1/thirst-for-identity",
                "set": "fra",
                "set_name": "Reality Fracture",
                "released_at": "2026-10-02",
            },
        ]
        body = scanner.render_issue_body(candidates, date(2026, 9, 8), 42, notes="Quiet week.")
        assert "Scanned **42** new cards released or previewed since 2026-09-08." in body
        assert "## Infinity Stones" in body
        assert "- [ ] [The Mind Stone](https://scryfall.com/card/msh/21/the-mind-stone)" in body
        assert "(Marvel Super Heroes, 2026-06-26) — confidence: **high**" in body
        assert "  - Second stone." in body
        assert "## Thirsts" in body
        assert "[Thirst for Identity](https://scryfall.com/card/fra/1/thirst-for-identity)" in body
        assert body.index("## Infinity Stones") < body.index("## Thirsts")
        assert "## Notes from the model\n\nQuiet week." in body
        assert "supercycle_scanner.py reject" in body


# ------------------------------------------------------------------------- cli


class TestCli:
    def setup_method(self):
        self.runner = CliRunner()

    def test_reject_appends_and_dedupes(self, tmp_path):
        state_file = tmp_path / "state.json"
        args = ["reject", "Green Goblin, Nemesis", "--cycle", "Nemeses", "--reason", "epithet"]
        args += ["--state-file", str(state_file)]

        result = self.runner.invoke(scanner.app, args)
        assert result.exit_code == 0, result.output
        assert "Rejected" in result.output
        result = self.runner.invoke(scanner.app, args)
        assert "already rejected" in result.output

        state = scanner.load_state(state_file)
        assert state["rejected"] == [
            {"card": "Green Goblin, Nemesis", "cycle": "Nemeses", "reason": "epithet"}
        ]

    def test_scan_dry_run_lists_cards_without_touching_state(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(
            scanner, "fetch_new_cards", lambda since, session=None: [make_card("X")]
        )

        result = self.runner.invoke(
            scanner.app,
            ["scan", "--dry-run", "--since", "2026-09-01", "--state-file", str(state_file)],
        )

        assert result.exit_code == 0, result.output
        assert result.output.startswith("X | ")
        assert "candidates=0 evaluated=1" in result.output
        assert not state_file.exists()

    def test_scan_writes_issue_json_and_state(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        supercycles_file = tmp_path / "supercycles.yaml"
        supercycles_file.write_text(SUPERCYCLES_YAML)
        issue_file = tmp_path / "out" / "issue.md"
        json_file = tmp_path / "out" / "candidates.json"
        github_output = tmp_path / "github_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))

        cards = [make_card("The Mind Stone"), make_card("Irrelevant Card")]
        monkeypatch.setattr(scanner, "fetch_new_cards", lambda since, session=None: cards)
        judgement = {
            "candidates": [
                {
                    "card": "The Mind Stone",
                    "cycle": "Infinity Stones",
                    "confidence": "high",
                    "rationale": "Stone.",
                }
            ],
            "notes": "",
        }
        calls = {}

        def fake_judge(client, supercycles_yaml, cards, rejected, model):
            calls["model"] = model
            calls["names"] = [c["name"] for c in cards]
            return judgement

        monkeypatch.setattr(scanner, "judge_candidates", fake_judge)
        monkeypatch.setattr(scanner, "date", FrozenDate)

        result = self.runner.invoke(
            scanner.app,
            [
                "scan",
                "--since",
                "2026-09-01",
                "--issue-file",
                str(issue_file),
                "--json-file",
                str(json_file),
                "--model",
                "claude-test",
                "--state-file",
                str(state_file),
                "--supercycles-file",
                str(supercycles_file),
            ],
        )

        assert result.exit_code == 0, result.output
        assert calls == {"model": "claude-test", "names": ["The Mind Stone", "Irrelevant Card"]}
        assert "candidates=1 evaluated=2" in result.output
        assert (
            "[The Mind Stone](https://scryfall.com/card/msh/21/the-mind-stone)"
            in issue_file.read_text()
        )
        assert json.loads(json_file.read_text())[0]["card"] == "The Mind Stone"
        assert github_output.read_text() == "candidates=1\nevaluated=2\n"

        state = scanner.load_state(state_file)
        assert state["last_scan"] == "2026-09-15"
        assert state["evaluated"] == {
            "The Mind Stone": "2026-06-26",
            "Irrelevant Card": "2026-06-26",
        }
        assert state["proposed"] == [
            {"card": "The Mind Stone", "cycle": "Infinity Stones", "proposed_on": "2026-09-15"}
        ]

    def test_scan_skips_model_when_nothing_new(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(scanner, "fetch_new_cards", lambda since, session=None: [])
        monkeypatch.setattr(
            scanner,
            "judge_candidates",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")),
        )
        issue_file = tmp_path / "issue.md"

        result = self.runner.invoke(
            scanner.app,
            [
                "scan",
                "--since",
                "2026-09-01",
                "--issue-file",
                str(issue_file),
                "--state-file",
                str(state_file),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "candidates=0 evaluated=0" in result.output
        assert not issue_file.exists()
        assert scanner.load_state(state_file)["last_scan"] is not None

    def test_scan_defaults_since_to_last_scan(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        state = scanner.default_state()
        state["last_scan"] = "2026-08-20"
        scanner.save_state(state, state_file)
        seen = {}
        monkeypatch.setattr(
            scanner,
            "fetch_new_cards",
            lambda since, session=None: seen.setdefault("since", since) and [],
        )

        result = self.runner.invoke(
            scanner.app, ["scan", "--dry-run", "--state-file", str(state_file)]
        )

        assert result.exit_code == 0, result.output
        assert seen["since"] == date(2026, 8, 20)


class FrozenDate(date):
    """date subclass whose today() is fixed, for deterministic state tests."""

    @classmethod
    def today(cls):
        return cls(2026, 9, 15)
