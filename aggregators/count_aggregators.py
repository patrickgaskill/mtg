"""Aggregators that count various card properties."""

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from .base import Aggregator


class CountAggregator(Aggregator):
    """Generic counting aggregator for arbitrary key fields."""

    def __init__(
        self,
        name: str,
        display_name: str,
        key_fields: List[str],
        count_finishes: bool = False,
        description: str = "",
        explanation: str = "",
    ):
        super().__init__(name, display_name, description, explanation)
        self.data: Dict[Tuple, int] = defaultdict(int)
        self.cards: Dict[Tuple, Dict[str, Any]] = {}
        self.key_fields = key_fields
        self.count_finishes = count_finishes

        # Define column definitions for ag-grid
        self.column_defs = []
        for field in key_fields:
            col_def = {"field": field, "headerName": field.title()}
            # Add card link renderer for "name" fields
            if field == "name":
                col_def["cellRenderer"] = "cardLinkRenderer"
            self.column_defs.append(col_def)
        self.column_defs.append(
            {"field": "count", "headerName": "Count", "type": "numericColumn"}
        )

    def process_card(self, card: Dict[str, Any]) -> None:
        key = tuple(card.get(field) for field in self.key_fields)
        self.data[key] += len(card.get("finishes", [])) if self.count_finishes else 1
        # Keep reference to first card for scryfall data
        if key not in self.cards:
            self.cards[key] = card

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        result = []
        for key, count in self.data.items():
            row_data = {**dict(zip(self.key_fields, key)), "count": count}
            # Add scryfall data if we have a reference card
            if key in self.cards:
                card = self.cards[key]
                row_data["scryfall_uri"] = card.get("scryfall_uri", "")
                row_data["image_uri"] = (
                    card.get("image_uris", {}).get("normal", "")
                    if card.get("image_uris")
                    else ""
                )
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
        self.data: Dict[str, int] = defaultdict(int)
        self.column_defs = [
            {"field": "set", "headerName": "Set", "width": 100},
            {
                "field": "maxNumber",
                "headerName": "Max Collector Number",
                "type": "numericColumn",
                "sort": "desc",
            },
        ]

    def process_card(self, card: Dict[str, Any]) -> None:
        collector_number = card.get("collector_number")
        if collector_number is not None and collector_number.isdigit():
            key = card.get("set")
            collector_number = int(collector_number)
            self.data[key] = max(self.data[key], collector_number)

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {"set": key, "maxNumber": value}
            for key, value in sorted(
                self.data.items(), key=lambda x: x[1], reverse=True
            )
        ]
