"""Aggregators for analyzing creature type statistics."""

import re
from collections.abc import Iterable
from typing import Any

from mtg.card import Card, Face

from .base import Aggregator, FirstCardByKeyAggregator, card_columns, card_fields

# Color code to display name mapping
COLOR_NAMES = {
    "W": "White",
    "U": "Blue",
    "B": "Black",
    "R": "Red",
    "G": "Green",
}

CREATURE_TYPE_COLUMN = {"field": "creatureType", "headerName": "Creature Type", "width": 160}
COUNT_COLUMN = {"field": "count", "headerName": "Count", "width": 100, "type": "numericColumn"}


class CreatureTypeAggregator(FirstCardByKeyAggregator):
    """Keyed by each creature subtype of traditional cards.

    Changelings and other "all creature types" cards are skipped, since they
    would otherwise count toward every type.
    """

    traditional_only = True

    def keys(self, card: Card) -> Iterable[tuple[Any, Face | None]]:
        if card.is_all_creature_types:
            return ()
        return ((subtype, None) for subtype in card.creature_subtypes)

    def key_fields(self, key: Any) -> dict[str, Any]:
        return {"creatureType": key}


class CreatureTypeCountAggregator(CreatureTypeAggregator):
    """Count how many cards exist for each creature subtype."""

    name = "creature_type_count"
    display_name = "Creature Type Census"
    description = "Count of cards for each creature subtype"
    explanation = (
        "Counts how many distinct cards exist for each creature subtype, sorted ascending"
        " to highlight the rarest types. Excludes Changelings and other"
        ' "all creature types" cards.'
    )
    column_defs = [
        CREATURE_TYPE_COLUMN,
        {**COUNT_COLUMN, "sort": "asc"},
        *card_columns("Latest Card"),
    ]
    prefer_latest = True

    def sorted_items(self):
        return sorted(self.best.items(), key=lambda item: self.counts[item[0]])

    def extra_fields(self, key, _card, _face, /):
        return {"count": self.counts[key]}


class FirstCardByCreatureTypeAggregator(CreatureTypeAggregator):
    """Find the first card printed for each creature subtype."""

    name = "first_card_by_creature_type"
    display_name = "First Card by Creature Type"
    description = "First card printed for each creature subtype"
    explanation = (
        "The earliest printed card for each creature subtype, showing when each type was"
        ' introduced. Excludes Changelings and other "all creature types" cards.'
    )
    column_defs = [CREATURE_TYPE_COLUMN, *card_columns()]


class CreatureTypeCombinationCountAggregator(CreatureTypeAggregator):
    """Count cards for each unique creature subtype combination."""

    name = "creature_type_combinations"
    display_name = "Creature Type Combinations"
    description = "Unique creature subtype combinations and their first cards"
    explanation = (
        "Every unique combination of creature subtypes (e.g., Human Wizard, Elf Warrior),"
        " with the first card printed for each combination and how many cards share it."
    )
    column_defs = [
        {"field": "combination", "headerName": "Type Combination", "width": 250},
        COUNT_COLUMN,
        *card_columns(),
    ]

    def keys(self, card: Card) -> Iterable[tuple[Any, Face | None]]:
        if card.is_all_creature_types or not card.creature_subtypes:
            return ()
        return [(card.creature_subtypes, None)]

    def key_fields(self, key: tuple[str, ...]) -> dict[str, Any]:
        return {"combination": " ".join(key)}

    def extra_fields(self, key, _card, _face, /):
        return {"count": self.counts[key]}


class FirstCreatureTypeByColorAggregator(CreatureTypeAggregator):
    """Find the first card for each creature type in each color."""

    name = "first_creature_type_by_color"
    display_name = "First Creature Type by Color"
    description = "First card for each creature type in each color"
    explanation = (
        "The first card printed for each combination of creature type and color (e.g.,"
        " the first red Whale, the first green Giraffe), tracking when each type first"
        " appeared in each color."
    )
    column_defs = [
        CREATURE_TYPE_COLUMN,
        {"field": "color", "headerName": "Color", "width": 100},
        *card_columns(),
    ]
    type_filters = [
        {"field": "color", "label": label, "keyword": label}
        for label in ("White", "Blue", "Black", "Red", "Green", "Colorless")
    ]

    def keys(self, card: Card) -> Iterable[tuple[Any, Face | None]]:
        if card.is_all_creature_types:
            return ()
        colors = [COLOR_NAMES.get(c, c) for c in card.colors] or ["Colorless"]
        return (((subtype, color), None) for subtype in card.creature_subtypes for color in colors)

    def key_fields(self, key: tuple[str, str]) -> dict[str, Any]:
        subtype, color = key
        return {"creatureType": subtype, "color": color}


class FirstLegendaryByCreatureTypeAggregator(CreatureTypeAggregator):
    """Find the first legendary creature for each creature subtype."""

    name = "first_legendary_by_creature_type"
    display_name = "First Legendary by Creature Type"
    description = "First legendary creature for each creature subtype"
    explanation = (
        "The first legendary creature printed for each creature subtype. Many types"
        " existed for years before getting their first legendary representative."
    )
    column_defs = [CREATURE_TYPE_COLUMN, *card_columns("First Legendary")]

    def keys(self, card: Card) -> Iterable[tuple[Any, Face | None]]:
        if "Legendary" not in card.type_line:
            return ()
        return super().keys(card)


class TokenOnlyCreatureTypesAggregator(FirstCardByKeyAggregator):
    """Find creature types that have only been printed on tokens, never on real cards."""

    name = "token_only_creature_types"
    display_name = "Token-Only Creature Types"
    description = "Creature types that only exist on printed token cards"
    explanation = (
        "Creature types that have only appeared on printed token cards, never on a"
        " non-token card (e.g., Pentavite, Germ, Servo). Only tokens printed as physical"
        " token cards count; tokens that exist solely as in-game objects do not."
    )
    column_defs = [CREATURE_TYPE_COLUMN, *card_columns("Example Token")]

    def __init__(self, context=None):
        super().__init__(context)
        self.card_types: set[str] = set()

    def process_card(self, card: Card) -> None:
        if card.is_all_creature_types:
            return
        if card.is_token:
            super().process_card(card)
        elif card.is_traditional:
            self.card_types.update(card.creature_subtypes)

    def keys(self, card: Card) -> Iterable[tuple[Any, Face | None]]:
        return ((subtype, None) for subtype in card.creature_subtypes)

    def key_fields(self, key: str) -> dict[str, Any]:
        return {"creatureType": key}

    def sorted_items(self):
        return sorted(
            (item for item in self.best.items() if item[0] not in self.card_types),
            key=lambda item: item[0],
        )


class RulesOnlyCreatureTypesAggregator(Aggregator):
    """Find creature types in the comprehensive rules that have never appeared on any card."""

    name = "rules_only_creature_types"
    display_name = "Rules-Only Creature Types"
    description = "Creature types in the rules but never on any card"
    explanation = (
        "Creature types defined in the comprehensive rules that have never appeared on"
        " any card, not even on a printed token card (e.g., Camarid, Tetravite, Caribou)."
        " A type whose token exists only as an in-game object, never as a printed token"
        " card, still qualifies."
    )
    column_defs = [CREATURE_TYPE_COLUMN, *card_columns("First Text Mention")]

    def __init__(self, context=None):
        super().__init__(context)
        self.all_creature_types = self.context.type_lists.creature
        if not self.all_creature_types:
            self.warnings.append("Creature types not loaded; run `mtg update-types`")
        self.seen_types: set[str] = set()
        self.first_text_mention: dict[str, Card] = {}
        # One whole-word pattern for every type (longest first so "Time Lord"
        # wins over shorter overlaps), allowing simple plurals like "Camarids".
        # Whole-word matching keeps "Elf" from matching "itself".
        alternation = "|".join(
            re.escape(t) for t in sorted(self.all_creature_types, key=lambda t: -len(t))
        )
        self._type_pattern = (
            re.compile(rf"\b({alternation})(?:e?s)?\b") if self.all_creature_types else None
        )

    def process_card(self, card: Card) -> None:
        if card.is_all_creature_types:
            return

        self.seen_types.update(card.creature_subtypes)

        if not card.oracle_text or self._type_pattern is None:
            return

        for creature_type in set(self._type_pattern.findall(card.oracle_text)):
            existing = self.first_text_mention.get(creature_type)
            if existing is None or card.sort_key < existing.sort_key:
                self.first_text_mention[creature_type] = card

    def get_sorted_data(self) -> list[dict[str, Any]]:
        results = []
        for subtype in sorted(self.all_creature_types - self.seen_types):
            card = self.first_text_mention.get(subtype)
            if card:
                results.append({"creatureType": subtype, **card_fields(card)})
            else:
                results.append({"creatureType": subtype, "name": "", "set": "", "releaseDate": ""})
        return results
