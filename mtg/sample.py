"""Cut a small, real sample from Scryfall bulk data for tests.

The sample combines named edge-case cards (a few printings each) with a stable
pseudo-random slice of everything else, chosen by hashing each card's id so the
same cards are picked from one bulk file to the next. Fields no report uses
(prices, legalities, purchase links, and so on) are dropped to keep it small.
"""

import gzip
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from mtg.card_utils import get_sort_key

# Cards whose layout, types, or history exercise edge cases in the reports.
SAMPLE_NAMES = (
    # Functional reprints
    "Llanowar Elves",
    "Fyndhorn Elves",
    # Double-faced, split, adventure, flip, meld
    "Delver of Secrets // Insectile Aberration",
    "Valakut Awakening // Valakut Stoneforge",
    "Bonecrusher Giant // Stomp",
    "Fire // Ice",
    "Akki Lavarunner // Tok-Tok, Volcano Born",
    "Brisela, Voice of Nightmares",
    "Summon: Choco/Mog",
    # All creature types, Kindred, mixed subtypes
    "Mistform Ultimus",
    "Changeling Outcast",
    "Nameless Inversion",
    "Faerie Trickery",
    "Urza's Saga",
    "Lizard Blades",
    "Obsidian Battle-Axe",
    "Dryad Arbor",
    "Faceless One",
    "Go-Shintai of Shared Purpose",
    "Gingerbrute",
    "Goldhound",
    "Lignify",
    "The Tenth Doctor",
    # Special cases in the maximal types reports
    "Grist, the Hunger Tide",
    "Planar Nexus",
    "Maskwood Nexus",
    "In Bolas's Clutches",
    "Omo, Queen of Vesuva",
    "Ashaya, Soul of the Wild",
    # Rules-only and token-only creature types
    "Homarid Spawning Bed",
    # Un-cards, playtest cards, memorabilia
    "Infinity Elemental",
    "Orb of Origin",
    "Black Lotus",
    # Many printings, finishes, and promos
    "Sol Ring",
    "Lightning Bolt",
    "Counterspell",
)

# Printings kept per named card: the earliest ones, which "first card" reports use.
PRINTINGS_PER_NAME = 4

# Keep about one in this many other cards.
RANDOM_SAMPLE_RATE = 300

# Top-level fields no report reads.
DROPPED_FIELDS = frozenset(
    {
        "arena_id",
        "cardmarket_id",
        "edhrec_rank",
        "games",
        "legalities",
        "mtgo_foil_id",
        "mtgo_id",
        "multiverse_ids",
        "penny_rank",
        "preview",
        "prices",
        "prints_search_uri",
        "purchase_uris",
        "related_uris",
        "resource_id",
        "rulings_uri",
        "scryfall_set_uri",
        "set_search_uri",
        "set_uri",
        "tcgplayer_etched_id",
        "tcgplayer_id",
        "uri",
    }
)


def _in_random_slice(card: dict[str, Any]) -> bool:
    card_id = card.get("id") or card.get("name") or ""
    digest = hashlib.sha1(card_id.encode(), usedforsecurity=False).digest()
    return int.from_bytes(digest[:8], "big") % RANDOM_SAMPLE_RATE == 0


def _trim(card: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in card.items() if key not in DROPPED_FIELDS}


def build_sample(
    cards: Iterable[dict[str, Any]], names: Iterable[str] = SAMPLE_NAMES
) -> list[dict[str, Any]]:
    """Select the sample from a stream of Scryfall card objects."""
    wanted = set(names)
    named: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sampled: list[dict[str, Any]] = []

    for card in cards:
        if card.get("name") in wanted:
            named[card["name"]].append(_trim(card))
        elif _in_random_slice(card):
            sampled.append(_trim(card))

    selected = sampled
    for printings in named.values():
        printings.sort(key=get_sort_key)
        selected.extend(printings[:PRINTINGS_PER_NAME])

    # A stable order keeps diffs of the (uncompressed) sample readable.
    return sorted(selected, key=lambda c: (c.get("name", ""), get_sort_key(c)))


def write_sample(cards: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # No name or mtime in the gzip header keeps its bytes identical when the cards are unchanged.
    with (
        path.open("wb") as raw,
        gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz,
    ):
        for card in cards:
            gz.write((json.dumps(card, ensure_ascii=False, sort_keys=True) + "\n").encode())
