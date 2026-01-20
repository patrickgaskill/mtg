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

    def __init__(self, supercycles_file: Path):
        super().__init__(
            name="supercycle_completion_time",
            display_name="Supercycle Completion Times",
            description="Time to complete supercycles",
            explanation="""
## What are Supercycles?

A **supercycle** (also called a **mega-mega cycle**) is a cycle of related cards distributed
across multiple sets that aren't confined to a single block. These cycles typically feature:

- Cards with shared mechanical or thematic elements
- Distributed representation across colors (often all five)
- Consistent mechanics with color-appropriate variations
- Thematic connections (legends from a plane, artifact types, creature classes)

## About This Report

This report tracks how long it took to complete each supercycle, measured from the release
date of the first card to the last card. For ongoing supercycles, the time shown is from
the first card to today's date.

**Examples of supercycles:**
- Tutors (five monocolored rare tutors from different sets)
- Elder Dragons (six three-colored legendary dragons with consistent abilities)
            """,
        )
        self.supercycles = self.load_supercycles(supercycles_file)
        self.card_dates: Dict[str, date] = {}
        self.card_data: Dict[str, Dict[str, Any]] = {}
        self.found_cards: Set[str] = set()
        self.column_defs = [
            {"field": "supercycle", "headerName": "Supercycle", "width": 200},
            {"field": "status", "headerName": "Status", "width": 120},
            {
                "field": "cards",
                "headerName": "Cards",
                "width": 400,
                "cellRenderer": "cardLinkRenderer",
                "cardLinkData": "cardObjects",
            },
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
                # Keep the earliest printing for Scryfall data
                self.card_data[name] = card

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

            # Collect card objects with Scryfall data for tooltips
            card_objects = []
            for card_name in cycle["cards"]:
                if card_name in self.card_data:
                    card = self.card_data[card_name]
                    card_objects.append(
                        {
                            "name": card_name,
                            "scryfall_uri": card.get("scryfall_uri", ""),
                            "image_uri": (
                                card.get("image_uris", {}).get("normal", "")
                                if card.get("image_uris")
                                else ""
                            ),
                        }
                    )

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
