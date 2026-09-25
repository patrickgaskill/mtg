"""Aggregators that analyze card metadata like promos, foils, and illustrations."""

from collections import defaultdict
from typing import Any

from mtg.card import Card
from mtg.constants import FOIL_PROMO_TYPES, MODERN_FOIL_CUTOFF_DATE, SPECIAL_FOIL_SETS

from .base import Aggregator


class CountCardIllustrationsBySetAggregator(Aggregator):
    """Count unique illustrations for each card in each set."""

    name = "count_card_illustrations_by_set"
    display_name = "Card Illustrations Count by Set"
    description = "Count of unique card illustrations by set"
    column_defs = [
        {"field": "set", "headerName": "Set", "width": 80},
        {
            "field": "name",
            "headerName": "Name",
            "width": 200,
            "cellRenderer": "cardLinkRenderer",
        },
        {
            "field": "count",
            "headerName": "Count",
            "width": 100,
            "type": "numericColumn",
            "sort": "desc",
        },
    ]

    def __init__(self, context=None):
        super().__init__(context)
        self.data: dict[tuple[str, str], set[str]] = defaultdict(set)
        self.cards: dict[tuple[str, str], dict[str, Any]] = {}

    def process_card(self, card: Card) -> None:
        set_ = card.set
        name = card.name
        illustration_id = card.illustration_key
        # Skip cards that lack a set or name to avoid aggregating them under empty keys.
        if not set_ or not name:
            return
        key = (set_, name)
        if illustration_id is not None:
            self.data[key].add(illustration_id)
        if key not in self.cards:
            self.cards[key] = card.link()

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                "set": set_,
                "name": name,
                "count": len(illustrations),
                **self.cards.get((set_, name), {}),
            }
            for (set_, name), illustrations in self.data.items()
        ]


class MostPrintingsSameArtAggregator(Aggregator):
    """Find cards with the most printings that all use the same illustration."""

    name = "most_printings_same_art"
    display_name = "Most Printings with Same Art"
    description = "Cards with the most printings using the same illustration"
    explanation = (
        "Cards with the most printings that all share the exact same illustration."
        " Cards with any alternate art across printings are excluded."
    )
    column_defs = [
        {
            "field": "name",
            "headerName": "Name",
            "width": 250,
            "cellRenderer": "cardLinkRenderer",
        },
        {
            "field": "printings",
            "headerName": "Printings",
            "width": 110,
            "type": "numericColumn",
            "sort": "desc",
        },
    ]

    def __init__(self, context=None):
        super().__init__(context)
        self.printings: dict[str, int] = defaultdict(int)
        self.illustrations: dict[str, set[str]] = defaultdict(set)
        self.cards: dict[str, dict[str, Any]] = {}

    def process_card(self, card: Card) -> None:
        name = card.name
        illustration_id = card.illustration_key
        if not name:
            return
        self.printings[name] += 1
        if illustration_id is not None:
            self.illustrations[name].add(illustration_id)
        if name not in self.cards:
            self.cards[name] = card.link()

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return sorted(
            [
                {
                    "name": name,
                    "printings": count,
                    **self.cards.get(name, {}),
                }
                for name, count in self.printings.items()
                if len(self.illustrations.get(name, set())) == 1
            ],
            key=lambda x: x["printings"],
            reverse=True,
        )


class MostUniqueIllustrationsAggregator(Aggregator):
    """Find cards with the most unique illustrations across all printings."""

    name = "most_unique_illustrations"
    display_name = "Most Unique Illustrations"
    description = "Cards with the most unique illustrations across printings"
    explanation = (
        "Cards with the most unique illustrations across all their printings, ranked by"
        " distinct illustration count."
    )
    column_defs = [
        {
            "field": "name",
            "headerName": "Name",
            "width": 250,
            "cellRenderer": "cardLinkRenderer",
        },
        {
            "field": "illustrations",
            "headerName": "Unique Illustrations",
            "width": 160,
            "type": "numericColumn",
            "sort": "desc",
        },
    ]

    def __init__(self, context=None):
        super().__init__(context)
        self.illustrations: dict[str, set[str]] = defaultdict(set)
        self.cards: dict[str, dict[str, Any]] = {}

    def process_card(self, card: Card) -> None:
        name = card.name
        illustration_id = card.illustration_key
        if not name or illustration_id is None:
            return
        self.illustrations[name].add(illustration_id)
        if name not in self.cards:
            self.cards[name] = card.link()

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return sorted(
            [
                {
                    "name": name,
                    "illustrations": len(ids),
                    **self.cards.get(name, {}),
                }
                for name, ids in self.illustrations.items()
                if len(ids) > 1
            ],
            key=lambda x: x["illustrations"],
            reverse=True,
        )


class PromoTypesAggregator(Aggregator):
    """Aggregate promo types by card name."""

    name = "promo_types_by_name"
    display_name = "Promo Types by Card Name"
    description = "Promo types by card name"
    column_defs = [
        {
            "field": "name",
            "headerName": "Name",
            "width": 160,
            "cellRenderer": "cardLinkRenderer",
        },
        {"field": "promoTypes", "headerName": "Promo Types", "width": 320},
        {
            "field": "numPromoTypes",
            "headerName": "Promo Type Count",
            "type": "numericColumn",
            "sort": "desc",
        },
    ]

    def __init__(self, context=None):
        super().__init__(context)
        self.data: dict[str, set[str]] = defaultdict(set)
        self.cards: dict[str, dict[str, Any]] = {}

    def process_card(self, card: Card) -> None:
        name = card.name
        # Skip cards without a name
        if not name:
            return
        promo_types = card.promo_types
        if promo_types:
            self.data[name].update(promo_types)
            if name not in self.cards:
                self.cards[name] = card.link()

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "promoTypes": ", ".join(sorted(promo_types)),
                "numPromoTypes": len(promo_types),
                **self.cards.get(name, {}),
            }
            for name, promo_types in self.data.items()
        ]


class FoilTypesAggregator(Aggregator):
    """Aggregate foil types by card name."""

    name = "foil_types_by_name"
    display_name = "Foil Types by Card Name"
    description = "Foil types by card name"
    column_defs = [
        {
            "field": "name",
            "headerName": "Name",
            "width": 200,
            "cellRenderer": "cardLinkRenderer",
        },
        {"field": "foilTypes", "headerName": "Foil Types", "width": 400},
        {
            "field": "numFoilTypes",
            "headerName": "Foil Type Count",
            "type": "numericColumn",
            "sort": "desc",
        },
    ]

    def __init__(self, context=None):
        super().__init__(context)
        self.data: dict[str, set[str]] = defaultdict(set)
        self.cards: dict[str, dict[str, Any]] = {}

    def process_card(self, card: Card) -> None:
        name = card.name
        # Skip cards without a name
        if not name:
            return
        set_ = card.set

        if name not in self.cards:
            self.cards[name] = card.link()

        # Handle special foil sets
        if set_ in SPECIAL_FOIL_SETS:
            self.data[name].add(SPECIAL_FOIL_SETS[set_])
            return

        # Filter promo types for actual foil types
        foil_promo_types = FOIL_PROMO_TYPES.intersection(card.promo_types)
        if foil_promo_types:
            self.data[name].update(foil_promo_types)

        # From the Vault have their own foil type
        if card.set_type == "from_the_vault":
            self.data[name].add("from_the_vault")

        # TODO: handle SDCC planeswalkers

        # Calculate which era of traditional foil applies
        if "foil" in card.finishes:
            if card.released_date and card.released_date < MODERN_FOIL_CUTOFF_DATE:
                self.data[name].add("premodern_foil")
            else:
                self.data[name].add("modern_foil")

        # Check for etched finish
        if "etched" in card.finishes:
            self.data[name].add("etched")

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "foilTypes": ", ".join(sorted(foil_types)),
                "numFoilTypes": len(foil_types),
                **self.cards.get(name, {}),
            }
            for name, foil_types in self.data.items()
        ]
