"""Aggregators that find the first card with specific characteristics."""

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from card_utils import generalize_mana_cost, get_sort_key

from .base import Aggregator


class FirstCardByPowerToughnessAggregator(Aggregator):
    """Find the first card printed for each power/toughness combination."""

    def __init__(self, description: str = ""):
        super().__init__(
            "first_card_by_power_toughness",
            "First Cards by Power and Toughness",
            description,
        )
        self.data: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.column_defs = [
            {"field": "power", "headerName": "Power", "width": 100},
            {"field": "toughness", "headerName": "Toughness", "width": 100},
            {"field": "name", "headerName": "Name", "width": 200},
            {"field": "set", "headerName": "Set", "width": 100},
            {"field": "releaseDate", "headerName": "Release Date", "width": 150},
        ]

    def process_card(self, card: Dict[str, Any]) -> None:
        power = card.get("power", "")
        toughness = card.get("toughness", "")

        if power == "" or toughness == "":
            return

        key = (power, toughness)

        if key not in self.data or get_sort_key(card) < get_sort_key(self.data[key]):
            self.data[key] = card

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {
                "power": power,
                "toughness": toughness,
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
            }
            for (power, toughness), card in sorted(
                self.data.items(), key=lambda item: get_sort_key(item[1])
            )
        ]


class FirstCardByGeneralizedManaCostAggregator(Aggregator):
    """Find the first card printed for each generalized mana cost."""

    def __init__(self, description: str = ""):
        super().__init__(
            "first_card_by_generalized_mana_cost",
            "First Cards by Generalized Mana Cost",
            description,
        )
        self.data: Dict[str, Dict[str, Any]] = {}
        self.count: Dict[str, int] = defaultdict(int)
        self.column_defs = [
            {
                "field": "generalizedManaCost",
                "headerName": "Generalized Mana Cost",
                "width": 120,
            },
            {"field": "name", "headerName": "Name", "width": 200},
            {"field": "set", "headerName": "Set", "width": 100},
            {"field": "releaseDate", "headerName": "Release Date", "width": 150},
            {
                "field": "originalManaCost",
                "headerName": "Original Mana Cost",
                "width": 150,
            },
            {"field": "count", "headerName": "Count", "type": "numericColumn"},
        ]

    def process_card(self, card: Dict[str, Any]) -> None:
        mana_cost = card.get("mana_cost")
        if mana_cost:
            generalized_cost = generalize_mana_cost(mana_cost)
            self.count[generalized_cost] += 1
            if generalized_cost not in self.data or get_sort_key(card) < get_sort_key(
                self.data[generalized_cost]
            ):
                self.data[generalized_cost] = card

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {
                "generalizedManaCost": generalized_cost,
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
                "originalManaCost": card.get("mana_cost", ""),
                "count": self.count[generalized_cost],
            }
            for generalized_cost, card in sorted(
                self.data.items(), key=lambda item: get_sort_key(item[1])
            )
        ]
