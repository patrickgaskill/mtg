"""Aggregators for analyzing creature type statistics."""

from collections import defaultdict
from pathlib import Path
from typing import Any

from card_utils import (
    get_card_link_data,
    get_sort_key,
    is_all_creature_types,
    is_traditional_card,
)

from .base import Aggregator

# Color code to display name mapping
COLOR_NAMES = {
    "W": "White",
    "U": "Blue",
    "B": "Black",
    "R": "Red",
    "G": "Green",
}


def extract_creature_subtypes(card: dict[str, Any]) -> set[str]:
    """Extract creature subtypes from a card's type line.

    Returns the set of subtypes for creature cards, or empty set if not a creature.
    Handles "Time Lord" as a single type and multi-faced cards.
    """
    type_line = card.get("type_line", "")

    # For double-faced cards, type_line contains both faces separated by " // "
    # Process each face separately
    faces = type_line.split(" // ")
    subtypes = set()

    for face in faces:
        # Check if this face is a creature
        if "—" not in face:
            continue

        supertypes_and_types, subtype_str = face.split("—", 1)

        if "Creature" not in supertypes_and_types:
            continue

        # Handle "Time Lord" as a single type
        subtype_str = subtype_str.replace("Time Lord", "Time-Lord")
        for part in subtype_str.split():
            subtypes.add(part.replace("Time-Lord", "Time Lord"))

    return subtypes


class CreatureTypeCountAggregator(Aggregator):
    """Count how many cards exist for each creature subtype."""

    def __init__(self, description: str = ""):
        super().__init__(
            "creature_type_count",
            "Creature Type Census",
            description,
            explanation="""
## Creature Type Census

This report counts how many distinct cards exist for each creature subtype. A card is
counted once per creature type it has — a "Human Wizard" adds one to both Human and Wizard.

**Filtering:**
- Only traditional cards are included (no silver-bordered, tokens, etc.)
- Changelings and similar "all creature types" cards are excluded from counts,
  since they would inflate every type equally

The count column shows the total number of cards with that creature type, sorted
ascending to highlight the rarest types.
            """,
        )
        self.counts: dict[str, int] = defaultdict(int)
        self.example_cards: dict[str, dict[str, Any]] = {}
        self.column_defs = [
            {"field": "creatureType", "headerName": "Creature Type", "width": 160},
            {
                "field": "count",
                "headerName": "Count",
                "width": 100,
                "type": "numericColumn",
                "sort": "asc",
            },
            {
                "field": "name",
                "headerName": "Latest Card",
                "width": 200,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 80},
            {"field": "releaseDate", "headerName": "Release Date", "width": 120},
        ]

    def process_card(self, card: dict[str, Any]) -> None:
        if not is_traditional_card(card):
            return
        if is_all_creature_types(card):
            return

        subtypes = extract_creature_subtypes(card)
        for subtype in subtypes:
            self.counts[subtype] += 1
            # Track the latest card for each type
            if subtype not in self.example_cards or get_sort_key(card) > get_sort_key(
                self.example_cards[subtype]
            ):
                self.example_cards[subtype] = card

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                "creatureType": subtype,
                "count": count,
                "name": self.example_cards[subtype].get("name", ""),
                "set": self.example_cards[subtype].get("set", ""),
                "releaseDate": self.example_cards[subtype].get("released_at", ""),
                **get_card_link_data(self.example_cards[subtype]),
            }
            for subtype, count in sorted(self.counts.items(), key=lambda x: x[1])
        ]


class FirstCardByCreatureTypeAggregator(Aggregator):
    """Find the first card printed for each creature subtype."""

    def __init__(self, description: str = ""):
        super().__init__(
            "first_card_by_creature_type",
            "First Card by Creature Type",
            description,
            explanation="""
## First Card by Creature Type

This report shows the earliest printed card for each creature subtype, revealing when
each type was introduced to Magic: The Gathering.

**Filtering:**
- Only traditional cards are included (no silver-bordered, tokens, etc.)
- Changelings and similar "all creature types" cards are excluded

Sorted by release date to show the history of creature type introductions.
            """,
        )
        self.first_cards: dict[str, dict[str, Any]] = {}
        self.column_defs = [
            {"field": "creatureType", "headerName": "Creature Type", "width": 160},
            {
                "field": "name",
                "headerName": "First Card",
                "width": 200,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 80},
            {"field": "releaseDate", "headerName": "Release Date", "width": 120},
        ]

    def process_card(self, card: dict[str, Any]) -> None:
        if not is_traditional_card(card):
            return
        if is_all_creature_types(card):
            return

        subtypes = extract_creature_subtypes(card)
        for subtype in subtypes:
            if subtype not in self.first_cards or get_sort_key(card) < get_sort_key(
                self.first_cards[subtype]
            ):
                self.first_cards[subtype] = card

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                "creatureType": subtype,
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
                **get_card_link_data(card),
            }
            for subtype, card in sorted(
                self.first_cards.items(), key=lambda item: get_sort_key(item[1])
            )
        ]


class CreatureTypeCombinationCountAggregator(Aggregator):
    """Count cards for each unique creature subtype combination."""

    def __init__(self, description: str = ""):
        super().__init__(
            "creature_type_combinations",
            "Creature Type Combinations",
            description,
            explanation="""
## Creature Type Combinations

This report tracks every unique combination of creature subtypes that has appeared on a
card. For example, "Human Wizard" and "Elf Warrior" are different combinations.

**Filtering:**
- Only traditional cards are included (no silver-bordered, tokens, etc.)
- Changelings and similar "all creature types" cards are excluded

Shows the first card printed with each combination and how many total cards share it.
Sorted by release date to highlight when new combinations were introduced.
            """,
        )
        self.counts: dict[tuple[str, ...], int] = defaultdict(int)
        self.first_cards: dict[tuple[str, ...], dict[str, Any]] = {}
        self.column_defs = [
            {"field": "combination", "headerName": "Type Combination", "width": 250},
            {
                "field": "count",
                "headerName": "Count",
                "width": 100,
                "type": "numericColumn",
            },
            {
                "field": "name",
                "headerName": "First Card",
                "width": 200,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 80},
            {"field": "releaseDate", "headerName": "Release Date", "width": 120},
        ]

    def process_card(self, card: dict[str, Any]) -> None:
        if not is_traditional_card(card):
            return
        if is_all_creature_types(card):
            return

        subtypes = extract_creature_subtypes(card)
        if not subtypes:
            return

        key = tuple(sorted(subtypes))
        self.counts[key] += 1
        if key not in self.first_cards or get_sort_key(card) < get_sort_key(self.first_cards[key]):
            self.first_cards[key] = card

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                "combination": " ".join(key),
                "count": self.counts[key],
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
                **get_card_link_data(card),
            }
            for key, card in sorted(
                self.first_cards.items(), key=lambda item: get_sort_key(item[1])
            )
        ]


class FirstCreatureTypeByColorAggregator(Aggregator):
    """Find the first card for each creature type in each color."""

    def __init__(self, description: str = ""):
        super().__init__(
            "first_creature_type_by_color",
            "First Creature Type by Color",
            description,
            explanation="""
## First Creature Type by Color

This report shows the first card printed for each combination of creature type and color.
For example, it tracks when the first red Whale or the first green Giraffe appeared.

**Colors tracked:** White (W), Blue (U), Black (B), Red (R), Green (G), and Colorless.

**Filtering:**
- Only traditional cards are included (no silver-bordered, tokens, etc.)
- Changelings and similar "all creature types" cards are excluded
- A card's colors come from the Scryfall `colors` field

This helps track "first time colors" — when a creature type first appeared in a new color.
            """,
        )
        # Key: (creature_type, color)
        self.first_cards: dict[tuple[str, str], dict[str, Any]] = {}
        self.column_defs = [
            {"field": "creatureType", "headerName": "Creature Type", "width": 160},
            {"field": "color", "headerName": "Color", "width": 100},
            {
                "field": "name",
                "headerName": "First Card",
                "width": 200,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 80},
            {"field": "releaseDate", "headerName": "Release Date", "width": 120},
        ]
        self.type_filters = [
            {"field": "color", "label": "White", "keyword": "White"},
            {"field": "color", "label": "Blue", "keyword": "Blue"},
            {"field": "color", "label": "Black", "keyword": "Black"},
            {"field": "color", "label": "Red", "keyword": "Red"},
            {"field": "color", "label": "Green", "keyword": "Green"},
            {"field": "color", "label": "Colorless", "keyword": "Colorless"},
        ]

    def process_card(self, card: dict[str, Any]) -> None:
        if not is_traditional_card(card):
            return
        if is_all_creature_types(card):
            return

        subtypes = extract_creature_subtypes(card)
        if not subtypes:
            return

        colors = card.get("colors", [])
        color_list = ["Colorless"] if not colors else [COLOR_NAMES.get(c, c) for c in colors]

        for subtype in subtypes:
            for color in color_list:
                key = (subtype, color)
                if key not in self.first_cards or get_sort_key(card) < get_sort_key(
                    self.first_cards[key]
                ):
                    self.first_cards[key] = card

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                "creatureType": subtype,
                "color": color,
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
                **get_card_link_data(card),
            }
            for (subtype, color), card in sorted(
                self.first_cards.items(), key=lambda item: get_sort_key(item[1])
            )
        ]


class FirstLegendaryByCreatureTypeAggregator(Aggregator):
    """Find the first legendary creature for each creature subtype."""

    def __init__(self, description: str = ""):
        super().__init__(
            "first_legendary_by_creature_type",
            "First Legendary by Creature Type",
            description,
            explanation="""
## First Legendary by Creature Type

This report shows the first legendary creature printed for each creature subtype.
Many creature types existed for years before getting their first legendary representative.

**Filtering:**
- Only traditional cards are included (no silver-bordered, tokens, etc.)
- Changelings and similar "all creature types" cards are excluded
- Only cards with "Legendary" in their type line are considered

Sorted by release date to show the progression of legendary creature type coverage.
            """,
        )
        self.first_cards: dict[str, dict[str, Any]] = {}
        self.column_defs = [
            {"field": "creatureType", "headerName": "Creature Type", "width": 160},
            {
                "field": "name",
                "headerName": "First Legendary",
                "width": 200,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 80},
            {"field": "releaseDate", "headerName": "Release Date", "width": 120},
        ]

    def process_card(self, card: dict[str, Any]) -> None:
        if not is_traditional_card(card):
            return
        if is_all_creature_types(card):
            return

        type_line = card.get("type_line", "")
        if "Legendary" not in type_line:
            return

        subtypes = extract_creature_subtypes(card)
        for subtype in subtypes:
            if subtype not in self.first_cards or get_sort_key(card) < get_sort_key(
                self.first_cards[subtype]
            ):
                self.first_cards[subtype] = card

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                "creatureType": subtype,
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
                **get_card_link_data(card),
            }
            for subtype, card in sorted(
                self.first_cards.items(), key=lambda item: get_sort_key(item[1])
            )
        ]


class TokenOnlyCreatureTypesAggregator(Aggregator):
    """Find creature types that have only been printed on tokens, never on real cards."""

    def __init__(self, description: str = ""):
        super().__init__(
            "token_only_creature_types",
            "Token-Only Creature Types",
            description,
            explanation="""
## Token-Only Creature Types

This report identifies creature types that have been printed on token cards but have
never appeared on a non-token card. These types exist in the game only as tokens.

Examples include types like Pentavite, Germ, Servo, and others that have only ever
been created by other cards' effects.

**How it works:**
- Scans all cards (including tokens) for creature subtypes
- Identifies types that appear on tokens but never on non-token traditional cards
- Changelings and similar "all creature types" cards are excluded
            """,
        )
        self.token_types: dict[str, dict[str, Any]] = {}
        self.card_types: set[str] = set()
        self.column_defs = [
            {"field": "creatureType", "headerName": "Creature Type", "width": 160},
            {
                "field": "name",
                "headerName": "Example Token",
                "width": 200,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 80},
            {"field": "releaseDate", "headerName": "Release Date", "width": 120},
        ]

    def process_card(self, card: dict[str, Any]) -> None:
        if is_all_creature_types(card):
            return

        layout = card.get("layout", "")
        is_token = layout == "token"

        subtypes = extract_creature_subtypes(card)

        if is_token:
            for subtype in subtypes:
                if subtype not in self.token_types or get_sort_key(card) < get_sort_key(
                    self.token_types[subtype]
                ):
                    self.token_types[subtype] = card
        elif is_traditional_card(card):
            self.card_types.update(subtypes)

    def get_sorted_data(self) -> list[dict[str, Any]]:
        token_only = {
            subtype: card
            for subtype, card in self.token_types.items()
            if subtype not in self.card_types
        }
        return [
            {
                "creatureType": subtype,
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
                **get_card_link_data(card),
            }
            for subtype, card in sorted(token_only.items(), key=lambda item: item[0])
        ]


class RulesOnlyCreatureTypesAggregator(Aggregator):
    """Find creature types in the comprehensive rules that have never appeared on any card."""

    def __init__(self, all_creature_types_file: Path, description: str = ""):
        super().__init__(
            "rules_only_creature_types",
            "Rules-Only Creature Types",
            description,
            explanation="""
## Rules-Only Creature Types

This report identifies creature types that exist in the MTG comprehensive rules but
have never been printed on any card — not even as a token. These types currently only
exist in rules text (e.g., as types created by specific card effects).

Examples include types like Camarid, Tetravite, Caribou, and others that are defined
in the rules but have never appeared on a physical or digital card.

**How it works:**
- Loads the official creature type list from the comprehensive rules
- Scans all cards (including tokens) for creature subtypes
- Reports types that are in the rules but never found on any card
- Changelings and similar "all creature types" cards are excluded from the scan

**Note:** The creature type list is updated via the `update-types` command.
            """,
        )
        self.all_creature_types = self._load_types(all_creature_types_file)
        self.seen_types: set[str] = set()
        self.first_text_mention: dict[str, dict[str, Any]] = {}
        self.column_defs = [
            {"field": "creatureType", "headerName": "Creature Type", "width": 160},
            {
                "field": "name",
                "headerName": "First Text Mention",
                "width": 200,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 80},
            {"field": "releaseDate", "headerName": "Release Date", "width": 120},
        ]

    def _load_types(self, file_path: Path) -> set[str]:
        """Load creature types from a text file."""
        try:
            with file_path.resolve().open("r") as f:
                return {line.strip() for line in f if line.strip()}
        except OSError as e:
            self.warnings.append(f"Error: Failed to load types from {file_path}: {e}")
            return set()

    def process_card(self, card: dict[str, Any]) -> None:
        if is_all_creature_types(card):
            return

        subtypes = extract_creature_subtypes(card)
        self.seen_types.update(subtypes)

        # Check oracle_text for mentions of rules-only types
        oracle_text = card.get("oracle_text", "")
        card_faces = card.get("card_faces")
        if card_faces:
            oracle_text = " ".join(face.get("oracle_text", "") for face in card_faces)

        if not oracle_text:
            return

        for creature_type in self.all_creature_types:
            if creature_type in oracle_text and (
                creature_type not in self.first_text_mention
                or get_sort_key(card) < get_sort_key(self.first_text_mention[creature_type])
            ):
                self.first_text_mention[creature_type] = card

    def get_sorted_data(self) -> list[dict[str, Any]]:
        rules_only = self.all_creature_types - self.seen_types
        results = []
        for subtype in sorted(rules_only):
            row: dict[str, Any] = {"creatureType": subtype}
            if subtype in self.first_text_mention:
                card = self.first_text_mention[subtype]
                row["name"] = card.get("name", "")
                row["set"] = card.get("set", "")
                row["releaseDate"] = card.get("released_at", "")
                row.update(get_card_link_data(card))
            else:
                row["name"] = ""
                row["set"] = ""
                row["releaseDate"] = ""
            results.append(row)
        return results
