"""Aggregators that count various card properties."""

from collections import defaultdict
from typing import Any

from mtg.card import Card
from mtg.constants import EXCLUDED_COLLECTOR_NUMBER_SETS

from .base import Aggregator


class CountAggregator(Aggregator):
    """Count cards (or their finishes) grouped by one or more Card fields.

    Subclasses set `key_fields` and, to count finish variations instead of
    printings, `count_finishes`.
    """

    key_fields: tuple[str, ...] = ()
    count_finishes: bool = False

    def __init__(self, context=None):
        super().__init__(context)
        self.data: dict[tuple[str, ...], int] = defaultdict(int)
        self.cards: dict[tuple[str, ...], dict[str, str]] = {}
        self.column_defs = [self._column_def(field) for field in self.key_fields] + [
            {"field": "count", "headerName": "Count", "width": 100, "type": "numericColumn"}
        ]

    @staticmethod
    def _column_def(field: str) -> dict[str, Any]:
        col_def: dict[str, Any] = {"field": field, "headerName": field.title()}
        if field == "name":
            col_def["cellRenderer"] = "cardLinkRenderer"
            col_def["width"] = 200
        elif field == "set":
            col_def["width"] = 80
        return col_def

    def process_card(self, card: Card) -> None:
        key = tuple(getattr(card, field) for field in self.key_fields)
        # Skip cards that are missing any key field.
        if not all(key):
            return
        self.data[key] += len(card.finishes) if self.count_finishes else 1
        if "name" in self.key_fields and key not in self.cards:
            self.cards[key] = card.link()

    def get_sorted_data(self) -> list[dict[str, Any]]:
        result = [
            {
                **dict(zip(self.key_fields, key, strict=True)),
                "count": count,
                **self.cards.get(key, {}),
            }
            for key, count in self.data.items()
        ]
        return sorted(result, key=lambda x: x["count"], reverse=True)


class CardsByNameAggregator(CountAggregator):
    name = "count_cards_by_name"
    display_name = "Cards by Name"
    description = "Count of unique cards by name"
    key_fields = ("name",)


class FinishesByNameAggregator(CountAggregator):
    name = "count_finishes_by_name"
    display_name = "Card Finishes by Name"
    description = "Count of card finishes by name"
    explanation = (
        "Counts the total number of finish variations (nonfoil, foil, etched) across all"
        " printings of each card name. A card printed in three sets with both foil and"
        " nonfoil would show a count of 6."
    )
    key_fields = ("name",)
    count_finishes = True


class CardsBySetAndNameAggregator(CountAggregator):
    name = "count_cards_by_set_name"
    display_name = "Cards by Set and Name"
    description = "Count of cards by set and name"
    key_fields = ("set", "name")


class FinishesBySetAndNameAggregator(CountAggregator):
    name = "count_finishes_by_set_name"
    display_name = "Card Finishes by Set and Name"
    description = "Count of card finishes by set and name"
    explanation = (
        "Counts how many finish variations (nonfoil, foil, etched) exist for each card"
        " within each specific set."
    )
    key_fields = ("set", "name")
    count_finishes = True


class MaxCollectorNumberBySetAggregator(Aggregator):
    """Find the maximum collector number for each set."""

    name = "max_collector_number_by_set"
    display_name = "Maximum Collector Number by Set"
    description = "Maximum collector number by set"
    explanation = (
        "The highest numeric collector number printed in each set. Sets where Scryfall"
        " invents collector numbers for cards that don't have real ones (e.g. Magic"
        " Online catalog IDs for the prm set, or event years for Vintage/Legacy"
        " Championship prints) are excluded."
    )
    column_defs = [
        {"field": "set", "headerName": "Set", "width": 80},
        {
            "field": "maxNumber",
            "headerName": "Max Collector Number",
            "width": 180,
            "type": "numericColumn",
            "sort": "desc",
        },
    ]

    def __init__(self, context=None):
        super().__init__(context)
        self.data: dict[str, int] = defaultdict(int)

    def process_card(self, card: Card) -> None:
        if not card.set or card.set in EXCLUDED_COLLECTOR_NUMBER_SETS:
            return
        if card.collector_number.isdigit():
            self.data[card.set] = max(self.data[card.set], int(card.collector_number))

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {"set": key, "maxNumber": value}
            for key, value in sorted(self.data.items(), key=lambda x: x[1], reverse=True)
        ]
