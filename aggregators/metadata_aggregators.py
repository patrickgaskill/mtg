"""Aggregators that analyze card metadata like promos, foils, and illustrations."""

from collections import defaultdict
from datetime import datetime
from typing import Any

from card_utils import get_card_link_data
from constants import FOIL_PROMO_TYPES, MODERN_FOIL_CUTOFF_DATE, SPECIAL_FOIL_SETS

from .base import Aggregator


class CountCardIllustrationsBySetAggregator(Aggregator):
    """Count unique illustrations for each card in each set."""

    def __init__(self, description: str = ""):
        super().__init__(
            "count_card_illustrations_by_set",
            "Card Illustrations Count by Set",
            description,
        )
        self.data: dict[tuple[str, str], set[str]] = defaultdict(set)
        self.cards: dict[tuple[str, str], dict[str, Any]] = {}
        self.column_defs = [
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

    def process_card(self, card: dict[str, Any]) -> None:
        set_ = card.get("set")
        name = card.get("name")
        illustration_id = card.get("illustration_id")
        # Skip cards that lack a set or name to avoid aggregating them under (None, ...) keys.
        if set_ is None or name is None:
            return
        key = (set_, name)
        if illustration_id is not None:
            self.data[key].add(illustration_id)
        if key not in self.cards:
            self.cards[key] = get_card_link_data(card)

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

    def __init__(self, description: str = ""):
        super().__init__(
            "most_printings_same_art",
            "Most Printings with Same Art",
            description,
            explanation="""
## What does this report show?

This report finds cards that have been printed the most times while always using
the **exact same piece of art** across every printing. For example, a card printed
in 30 different sets but always with the same illustration would rank highly here.

Cards that have received alternate art in any printing are excluded — every printing
must share a single `illustration_id` in the Scryfall data.

Inspired by [this Reddit discussion](https://www.reddit.com/r/magicTCG/comments/1sbk27u/)
about Krosan Tusker's many printings with the same art.
            """,
        )
        self.printings: dict[str, int] = defaultdict(int)
        self.illustrations: dict[str, set[str]] = defaultdict(set)
        self.cards: dict[str, dict[str, Any]] = {}
        self.column_defs = [
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

    def process_card(self, card: dict[str, Any]) -> None:
        name = card.get("name")
        illustration_id = card.get("illustration_id")
        if name is None:
            return
        self.printings[name] += 1
        if illustration_id is not None:
            self.illustrations[name].add(illustration_id)
        if name not in self.cards:
            self.cards[name] = get_card_link_data(card)

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

    def __init__(self, description: str = ""):
        super().__init__(
            "most_unique_illustrations",
            "Most Unique Illustrations",
            description,
            explanation="""
## What does this report show?

This report finds cards that have been illustrated by the most different artists
or received the most alternate art treatments across all their printings. Each
unique `illustration_id` in the Scryfall data represents a distinct piece of art.

Cards that have been reprinted many times with new art (like Lightning Bolt or
Birds of Paradise) will rank highly here.
            """,
        )
        self.illustrations: dict[str, set[str]] = defaultdict(set)
        self.cards: dict[str, dict[str, Any]] = {}
        self.column_defs = [
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

    def process_card(self, card: dict[str, Any]) -> None:
        name = card.get("name")
        illustration_id = card.get("illustration_id")
        if name is None or illustration_id is None:
            return
        self.illustrations[name].add(illustration_id)
        if name not in self.cards:
            self.cards[name] = get_card_link_data(card)

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

    def __init__(self, description: str = ""):
        super().__init__("promo_types_by_name", "Promo Types by Card Name", description)
        self.data: dict[str, set[str]] = defaultdict(set)
        self.cards: dict[str, dict[str, Any]] = {}
        self.column_defs = [
            {
                "field": "name",
                "headerName": "Name",
                "width": 160,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "promoTypes", "headerName": "Promo Types", "width": 320},
            {
                "field": "count",
                "headerName": "Count",
                "type": "numericColumn",
                "sort": "desc",
            },
        ]

    def process_card(self, card: dict[str, Any]) -> None:
        name = card.get("name")
        # Skip cards without a name
        if name is None:
            return
        promo_types = card.get("promo_types", [])
        if promo_types:
            self.data[name].update(promo_types)
            if name not in self.cards:
                self.cards[name] = get_card_link_data(card)

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "promoTypes": ", ".join(sorted(promo_types)),
                "count": len(promo_types),
                **self.cards.get(name, {}),
            }
            for name, promo_types in self.data.items()
        ]


class FoilTypesAggregator(Aggregator):
    """Aggregate foil types by card name."""

    def __init__(self, description: str = ""):
        super().__init__("foil_types_by_name", "Foil Types by Card Name", description)
        self.data: dict[str, set[str]] = defaultdict(set)
        self.cards: dict[str, dict[str, Any]] = {}
        self.column_defs = [
            {
                "field": "name",
                "headerName": "Name",
                "width": 200,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "foilTypes", "headerName": "Foil Types", "width": 400},
            {
                "field": "count",
                "headerName": "Count",
                "type": "numericColumn",
                "sort": "desc",
            },
        ]

    def process_card(self, card: dict[str, Any]) -> None:
        name = card.get("name")
        # Skip cards without a name
        if name is None:
            return
        set_ = card.get("set")

        if name not in self.cards:
            self.cards[name] = get_card_link_data(card)

        # Handle special foil sets
        if set_ in SPECIAL_FOIL_SETS:
            self.data[name].add(SPECIAL_FOIL_SETS[set_])
            return

        # Filter promo types for actual foil types
        promo_types = card.get("promo_types", [])
        if promo_types:
            self.data[name].update(p for p in promo_types if p in FOIL_PROMO_TYPES)

        # From the Vault have their own foil type
        set_type = card.get("set_type")
        if set_type == "from_the_vault":
            self.data[name].add("from_the_vault")

        # TODO: handle SDCC planeswalkers

        # Calculate which era of traditional foil applies
        finishes = card.get("finishes", [])
        if "foil" in finishes:
            release_date_str = card.get("released_at")
            if release_date_str:
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d")
                if release_date < MODERN_FOIL_CUTOFF_DATE:
                    self.data[name].add("premodern_foil")
                else:
                    self.data[name].add("modern_foil")
            else:
                self.data[name].add("modern_foil")

        # Check for etched finish
        if "etched" in finishes:
            self.data[name].add("etched")

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "foilTypes": ", ".join(sorted(foil_types)),
                "count": len(foil_types),
                **self.cards.get(name, {}),
            }
            for name, foil_types in self.data.items()
        ]
