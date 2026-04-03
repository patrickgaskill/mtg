"""Aggregators that find the first card with specific characteristics."""

from collections import defaultdict
from typing import Any

from card_utils import generalize_mana_cost, get_card_link_data, get_sort_key

from .base import Aggregator


class FirstCardByPowerToughnessAggregator(Aggregator):
    """Find the first card printed for each power/toughness combination."""

    def __init__(self, description: str = ""):
        super().__init__(
            "first_card_by_power_toughness",
            "First Cards by Power and Toughness",
            description,
        )
        self.data: dict[tuple[str, str], dict[str, Any]] = {}
        self.column_defs = [
            {"field": "power", "headerName": "Power", "width": 90},
            {"field": "toughness", "headerName": "Toughness", "width": 110},
            {
                "field": "name",
                "headerName": "Name",
                "width": 200,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 80},
            {"field": "releaseDate", "headerName": "Release Date", "width": 120},
        ]

    def process_card(self, card: dict[str, Any]) -> None:
        power = card.get("power", "")
        toughness = card.get("toughness", "")

        if power == "" or toughness == "":
            return

        key = (power, toughness)

        if key not in self.data or get_sort_key(card) < get_sort_key(self.data[key]):
            self.data[key] = card

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                "power": power,
                "toughness": toughness,
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
                **get_card_link_data(card),
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
        self.data: dict[str, dict[str, Any]] = {}
        self.original_mana_costs: dict[str, str] = {}
        self.count: dict[str, int] = defaultdict(int)
        self.column_defs = [
            {
                "field": "generalizedManaCost",
                "headerName": "Generalized Mana Cost",
                "width": 200,
            },
            {
                "field": "name",
                "headerName": "Name",
                "width": 200,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 80},
            {"field": "releaseDate", "headerName": "Release Date", "width": 120},
            {
                "field": "originalManaCost",
                "headerName": "Original Mana Cost",
                "width": 180,
            },
            {"field": "count", "headerName": "Count", "width": 100, "type": "numericColumn"},
        ]

    def _process_mana_cost(self, mana_cost: str, card: dict[str, Any]) -> None:
        generalized_cost = generalize_mana_cost(mana_cost)
        self.count[generalized_cost] += 1
        if generalized_cost not in self.data or get_sort_key(card) < get_sort_key(
            self.data[generalized_cost]
        ):
            self.data[generalized_cost] = card
            self.original_mana_costs[generalized_cost] = mana_cost

    def process_card(self, card: dict[str, Any]) -> None:
        card_faces = card.get("card_faces")
        if card_faces:
            for face in card_faces:
                mana_cost = face.get("mana_cost")
                if mana_cost:
                    self._process_mana_cost(mana_cost, card)
        else:
            mana_cost = card.get("mana_cost")
            if mana_cost:
                self._process_mana_cost(mana_cost, card)

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                "generalizedManaCost": generalized_cost,
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
                "originalManaCost": self.original_mana_costs.get(generalized_cost, ""),
                "count": self.count[generalized_cost],
                **get_card_link_data(card),
            }
            for generalized_cost, card in sorted(
                self.data.items(), key=lambda item: get_sort_key(item[1])
            )
        ]
