"""Aggregators that analyze card metadata like promos, foils, and illustrations."""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

from card_utils import get_card_image_uri

from .base import Aggregator
from .constants import FOIL_PROMO_TYPES, MODERN_FOIL_CUTOFF_DATE, SPECIAL_FOIL_SETS


class CountCardIllustrationsBySetAggregator(Aggregator):
    """Count unique illustrations for each card in each set."""

    def __init__(self, description: str = ""):
        super().__init__(
            "count_card_illustrations_by_set",
            "Card Illustrations Count by Set",
            description,
        )
        self.data: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        self.cards: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.column_defs = [
            {"field": "set", "headerName": "Set"},
            {
                "field": "name",
                "headerName": "Name",
                "cellRenderer": "cardLinkRenderer",
            },
            {
                "field": "count",
                "headerName": "Count",
                "type": "numericColumn",
                "sort": "desc",
            },
        ]

    def process_card(self, card: Dict[str, Any]) -> None:
        set_ = card.get("set")
        name = card.get("name")
        # Skip cards that lack a set or name to avoid aggregating them under (None, ...) keys.
        if set_ is None or name is None:
            return
        key = (set_, name)
        self.data[key].add(card.get("illustration_id"))
        # Keep minimal Scryfall data to reduce memory usage
        # Note: Stores first encountered printing's link/image per (set, name).
        # For illustration counting, showing any printing from the set is acceptable.
        # Empty strings are stored for missing data - the JavaScript renderer handles this
        # by falling back to Scryfall search.
        if key not in self.cards:
            self.cards[key] = {
                "scryfall_uri": card.get("scryfall_uri", ""),
                "image_uri": get_card_image_uri(card),
            }

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {
                "set": set_,
                "name": name,
                "count": len(illustrations),
                **self.cards.get((set_, name), {}),
            }
            for (set_, name), illustrations in self.data.items()
        ]


class PromoTypesAggregator(Aggregator):
    """Aggregate promo types by card name."""

    def __init__(self, description: str = ""):
        super().__init__("promo_types_by_name", "Promo Types by Card Name", description)
        self.data: Dict[str, Set[str]] = defaultdict(set)
        self.cards: Dict[str, Dict[str, Any]] = {}
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

    def process_card(self, card: Dict[str, Any]) -> None:
        name = card.get("name")
        promo_types = card.get("promo_types", [])
        if promo_types:
            self.data[name].update(promo_types)
            # Keep minimal Scryfall data to reduce memory usage
            # Note: Stores first encountered printing's link/image per card name.
            # Shows any representative printing; promo type aggregation is the focus, not specific versions.
            # Empty strings for missing data are handled by JavaScript renderer fallback.
            if name not in self.cards:
                self.cards[name] = {
                    "scryfall_uri": card.get("scryfall_uri", ""),
                    "image_uri": get_card_image_uri(card),
                }

    def get_sorted_data(self) -> List[Dict[str, Any]]:
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
        self.data: Dict[str, Set[str]] = defaultdict(set)
        self.cards: Dict[str, Dict[str, Any]] = {}
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

    def process_card(self, card: Dict[str, Any]) -> None:
        name = card.get("name")
        set_ = card.get("set")

        # Keep minimal Scryfall data to reduce memory usage
        # Note: Stores first encountered printing's link/image per card name.
        # Shows any representative printing; foil type aggregation is the focus, not specific versions.
        if name not in self.cards:
            self.cards[name] = {
                "scryfall_uri": card.get("scryfall_uri", ""),
                "image_uri": get_card_image_uri(card),
            }

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

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "foilTypes": ", ".join(sorted(foil_types)),
                "count": len(foil_types),
                **self.cards.get(name, {}),
            }
            for name, foil_types in self.data.items()
        ]
