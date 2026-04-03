"""Aggregators for supercycle completion times."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from card_utils import get_card_image_uri

from .base import Aggregator


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

    def __init__(self, supercycles_file: Path):
        super().__init__(
            name="supercycle_completion_time",
            display_name="Supercycle Completion Times",
            description="Time to complete supercycles",
            explanation='Learn more about supercycles on the <a href="https://mtg.fandom.com/wiki/Mega_mega_cycle" target="_blank" rel="noopener noreferrer">MTG Wiki</a>.',
        )
        self.supercycles = self.load_supercycles(supercycles_file)
        self.card_dates: dict[str, date] = {}
        self.card_data: dict[str, dict[str, Any]] = {}
        self.found_cards: set[str] = set()
        self.column_defs = [
            {"field": "supercycle", "headerName": "Supercycle", "width": 220},
            {"field": "status", "headerName": "Status", "width": 100},
            {
                "field": "cards",
                "headerName": "Cards",
                "width": 280,
                "wrapText": True,
                "autoHeight": True,
                "suppressAutoSize": True,
                "cellClass": "compact-cell",
                "cellRenderer": "cardLinkRenderer",
                "cardLinkData": "cardObjects",
            },
            {"field": "time", "headerName": "Time", "width": 150},
            {"field": "startDate", "headerName": "Start Date", "width": 120},
            {"field": "endDate", "headerName": "End Date", "width": 120},
        ]

    def load_supercycles(self, file_path: Path) -> dict[str, dict[str, Any]]:
        """Load supercycles from YAML or JSON file."""
        try:
            with file_path.open("r", encoding="utf-8") as f:
                if file_path.suffix.lower() == ".yaml" or file_path.suffix.lower() == ".yml":
                    data = yaml.safe_load(f)
                else:
                    # Fallback to JSON for backward compatibility
                    data = json.load(f)
                return {cycle["name"]: cycle for cycle in data["supercycles"]}
        except OSError as e:
            self.warnings.append(f"Error: Failed to load supercycles from {file_path}: {e}")
            return {}
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            self.warnings.append(f"Error: Failed to parse supercycles file {file_path}: {e}")
            return {}

    def process_card(self, card: dict[str, Any]) -> None:
        name = card.get("name")
        released_at = card.get("released_at")
        if name and released_at:
            card_date = date.fromisoformat(released_at)
            if name not in self.card_dates or card_date < self.card_dates[name]:
                self.card_dates[name] = card_date
                # Keep minimal Scryfall data to reduce memory usage.
                # Empty strings for missing data are handled by JavaScript renderer fallback.
                self.card_data[name] = {
                    "name": name,
                    "scryfall_uri": card.get("scryfall_uri", ""),
                    "image_uri": get_card_image_uri(card),
                }

    def get_sorted_data(self) -> list[dict[str, Any]]:
        today = date.today()
        result = []

        for name, cycle in self.supercycles.items():
            card_dates = [
                self.card_dates.get(card) for card in cycle["cards"] if card in self.card_dates
            ]
            if not card_dates:
                continue

            earliest_date = min(card_dates)
            latest_date = max(card_dates) if cycle["finished"] else today

            days = (latest_date - earliest_date).days
            status = "Finished" if cycle["finished"] else "Unfinished"
            formatted_time = format_time_difference(days)

            # Collect card objects with Scryfall data for tooltips
            card_objects = []
            for card_name in cycle["cards"]:
                if card_name in self.card_data:
                    card_objects.append(self.card_data[card_name])
                else:
                    self.warnings.append(
                        f"Supercycle '{name}' references card '{card_name}' with no processed data"
                    )

            if not card_objects:
                self.warnings.append(
                    f"Error: Supercycle '{name}' has no valid card data; skipping from results"
                )
                continue

            result.append(
                {
                    "supercycle": name,
                    "status": status,
                    "cards": ", ".join(cycle["cards"]),
                    "cardObjects": card_objects,
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
