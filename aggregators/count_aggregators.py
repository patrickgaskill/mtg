"""Aggregators that count various card properties."""

from collections import defaultdict
from typing import Any

from card_utils import get_card_image_uri

from .base import Aggregator


class CountAggregator(Aggregator):
    """Generic counting aggregator for arbitrary key fields."""

    def __init__(
        self,
        name: str,
        display_name: str,
        key_fields: list[str],
        count_finishes: bool = False,
        description: str = "",
        explanation: str = "",
    ):
        super().__init__(name, display_name, description, explanation)
        self.data: dict[tuple, int] = defaultdict(int)
        self.cards: dict[tuple, dict[str, Any]] = {}
        self.key_fields = key_fields
        self.count_finishes = count_finishes
        self.needs_card_links = "name" in key_fields

        # Define column definitions for ag-grid
        self.column_defs = []
        for field in key_fields:
            col_def = {"field": field, "headerName": field.title()}
            # Add card link renderer for "name" fields
            # Note: This requires process_card to store Scryfall data (see process_card method)
            if field == "name":
                col_def["cellRenderer"] = "cardLinkRenderer"
                col_def["width"] = 200
            elif field == "set":
                col_def["width"] = 80
            self.column_defs.append(col_def)
        self.column_defs.append(
            {"field": "count", "headerName": "Count", "width": 100, "type": "numericColumn"}
        )

    def process_card(self, card: dict[str, Any]) -> None:
        # Build key values and skip cards that are missing any required key field.
        key_values = [card.get(field) for field in self.key_fields]
        if any(value is None for value in key_values):
            return
        key = tuple(key_values)
        self.data[key] += len(card.get("finishes", [])) if self.count_finishes else 1
        # Keep minimal Scryfall data to reduce memory usage (only when "name" is a key field)
        # Note: Stores first encountered printing's link/image. For count aggregators,
        # showing any printing is acceptable since the focus is on counts, not specific versions.
        # Empty strings are stored for missing data - this is intentional as the JavaScript
        # CardLinkRenderer handles null/empty values by falling back to Scryfall search.
        if self.needs_card_links and key not in self.cards:
            self.cards[key] = {
                "scryfall_uri": card.get("scryfall_uri", ""),
                "image_uri": get_card_image_uri(card),
            }

    def get_sorted_data(self) -> list[dict[str, Any]]:
        result = []
        for key, count in self.data.items():
            row_data = {**dict(zip(self.key_fields, key)), "count": count}
            # Add scryfall data if available
            if key in self.cards:
                row_data.update(self.cards[key])
            result.append(row_data)
        return sorted(result, key=lambda x: x["count"], reverse=True)


class MaxCollectorNumberBySetAggregator(Aggregator):
    """Find the maximum collector number for each set."""

    def __init__(self, description: str = ""):
        super().__init__(
            "max_collector_number_by_set",
            "Maximum Collector Number by Set",
            description,
        )
        self.data: dict[str, int] = defaultdict(int)
        self.column_defs = [
            {"field": "set", "headerName": "Set", "width": 80},
            {
                "field": "maxNumber",
                "headerName": "Max Collector Number",
                "width": 180,
                "type": "numericColumn",
                "sort": "desc",
            },
        ]

    def process_card(self, card: dict[str, Any]) -> None:
        collector_number = card.get("collector_number")
        key = card.get("set")
        if collector_number is not None and collector_number.isdigit() and key is not None:
            collector_number = int(collector_number)
            self.data[key] = max(self.data[key], collector_number)

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {"set": key, "maxNumber": value}
            for key, value in sorted(self.data.items(), key=lambda x: x[1], reverse=True)
        ]
