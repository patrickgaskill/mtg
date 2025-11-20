"""Aggregators for supercycle completion times."""

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml

from .base import Aggregator, logger


def format_time_difference(days: int) -> str:
    """Format a time difference in days into a human-readable string."""
    years, remaining_days = divmod(days, 365)
    months, days = divmod(remaining_days, 30)

    parts = []
    if years > 0:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months > 0:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")

    return ", ".join(parts)


class SupercycleTimeAggregator(Aggregator):
    """Track completion times for card supercycles."""

    def __init__(self, supercycles_file: Path, description: str = ""):
        super().__init__(
            "supercycle_completion_time", "Supercycle Completion Times", description
        )
        self.supercycles = self.load_supercycles(supercycles_file)
        self.card_dates: Dict[str, date] = {}
        self.found_cards: Set[str] = set()
        self.column_defs = [
            {"field": "supercycle", "headerName": "Supercycle", "width": 200},
            {"field": "status", "headerName": "Status", "width": 120},
            {"field": "time", "headerName": "Time", "width": 200},
            {"field": "startDate", "headerName": "Start Date", "width": 150},
            {"field": "endDate", "headerName": "End Date", "width": 150},
        ]

    def load_supercycles(self, file_path: Path) -> Dict[str, Dict[str, Any]]:
        """Load supercycles from YAML or JSON file."""
        try:
            with file_path.open("r", encoding="utf-8") as f:
                if (
                    file_path.suffix.lower() == ".yaml"
                    or file_path.suffix.lower() == ".yml"
                ):
                    data = yaml.safe_load(f)
                else:
                    # Fallback to JSON for backward compatibility
                    data = json.load(f)
                return {cycle["name"]: cycle for cycle in data["supercycles"]}
        except IOError as e:
            logger.error(f"Failed to load supercycles from {file_path}: {e}")
            return {}
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse supercycles file {file_path}: {e}")
            return {}

    def process_card(self, card: Dict[str, Any]) -> None:
        name = card.get("name")
        released_at = card.get("released_at")
        if name and released_at:
            card_date = date.fromisoformat(released_at)
            if name not in self.card_dates or card_date < self.card_dates[name]:
                self.card_dates[name] = card_date

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        today = date.today()
        result = []

        for name, cycle in self.supercycles.items():
            card_dates = [
                self.card_dates.get(card)
                for card in cycle["cards"]
                if card in self.card_dates
            ]
            if not card_dates:
                continue

            earliest_date = min(card_dates)
            if cycle["finished"]:
                latest_date = max(card_dates)
            else:
                latest_date = today

            days = (latest_date - earliest_date).days
            status = "Finished" if cycle["finished"] else "Unfinished"
            formatted_time = format_time_difference(days)
            result.append(
                {
                    "supercycle": name,
                    "status": status,
                    "time": formatted_time,
                    "startDate": earliest_date.strftime("%B %d, %Y"),
                    "endDate": latest_date.strftime("%B %d, %Y")
                    if cycle["finished"]
                    else "Ongoing",
                    "days": days,  # Store for sorting
                }
            )

        # Sort by actual day count in descending order
        return sorted(result, key=lambda x: x["days"], reverse=True)
