"""Aggregators for supercycle completion times."""

import calendar
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from mtg.card import Card
from mtg.supercycles import Supercycle, load_supercycles

from .base import Aggregator


def format_time_difference(start_date: date, end_date: date) -> str:
    """Format a time difference between two dates into a human-readable string."""
    years = end_date.year - start_date.year
    months = end_date.month - start_date.month
    days = end_date.day - start_date.day

    if days < 0:
        months -= 1
        prev_month = end_date.month - 1 if end_date.month > 1 else 12
        prev_year = end_date.year if end_date.month > 1 else end_date.year - 1
        days += calendar.monthrange(prev_year, prev_month)[1]

    if months < 0:
        years -= 1
        months += 12

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

    name = "supercycle_completion_time"
    display_name = "Supercycle Completion Times"
    description = "Time to complete supercycles"
    explanation = (
        "Learn more about supercycles on the"
        ' <a href="https://mtg.fandom.com/wiki/Mega_mega_cycle"'
        ' target="_blank" rel="noopener noreferrer">MTG Wiki</a>.'
    )
    column_defs = [
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

    def __init__(self, context=None):
        super().__init__(context)
        supercycles_file = self.context.supercycles_file
        self.supercycles = self.load_supercycles(supercycles_file) if supercycles_file else []
        if supercycles_file is None:
            self.warnings.append("No supercycles file configured")
        self.card_dates: dict[str, date] = {}
        self.card_data: dict[str, dict[str, Any]] = {}
        self.ruled_cycles = [cycle for cycle in self.supercycles if cycle.match]
        # Per cycle, the earliest printing of each card its rule suggests adding.
        self.candidates: dict[str, dict[str, Card]] = {}
        # Listed cards that some printing of fits their cycle's rule.
        self.matched_members: set[tuple[str, str]] = set()

    def load_supercycles(self, file_path: Path) -> list[Supercycle]:
        try:
            return load_supercycles(file_path)
        except OSError as e:
            self.warnings.append(f"Error: Failed to load supercycles from {file_path}: {e}")
        except (yaml.YAMLError, ValueError) as e:
            self.warnings.append(f"Error: Failed to parse supercycles file {file_path}: {e}")
        return []

    def process_card(self, card: Card) -> None:
        name = card.name
        card_date = card.released_date
        if (
            name
            and card_date
            and (name not in self.card_dates or card_date < self.card_dates[name])
        ):
            self.card_dates[name] = card_date
            # Empty strings for missing data are handled by JavaScript renderer fallback.
            self.card_data[name] = {"name": name, **card.link()}

        for cycle in self.ruled_cycles:
            if cycle.is_candidate(card):
                found = self.candidates.setdefault(cycle.name, {})
                if name not in found or card.sort_key < found[name].sort_key:
                    found[name] = card
            elif name in cycle.cards and cycle.match and cycle.match.matches(card):
                self.matched_members.add((cycle.name, name))

    def candidate_rows(self) -> list[dict[str, str]]:
        """New-member candidates, by cycle (in file order) and then by release."""
        rows = []
        for cycle in self.ruled_cycles:
            for card in sorted(
                self.candidates.get(cycle.name, {}).values(), key=lambda c: c.sort_key
            ):
                rows.append(
                    {
                        "supercycle": cycle.name,
                        "name": card.name,
                        "set": card.set,
                        "releaseDate": card.released_at,
                        "scryfall_uri": card.scryfall_uri,
                    }
                )
        return rows

    def unmatched_members(self) -> list[tuple[str, str]]:
        """Listed cards (that were seen) no printing of fits their cycle's rule."""
        return [
            (cycle.name, card)
            for cycle in self.ruled_cycles
            for card in cycle.cards
            if card in self.card_dates and (cycle.name, card) not in self.matched_members
        ]

    def get_sorted_data(self) -> list[dict[str, Any]]:
        today = self.context.today()
        result = []

        for row in self.candidate_rows():
            self.warnings.append(
                f"Supercycle '{row['supercycle']}' may have a new member: "
                f"{row['name']} ({row['set']}, {row['releaseDate']})"
            )
        for cycle_name, card in self.unmatched_members():
            self.warnings.append(
                f"Supercycle '{cycle_name}' rule doesn't match its listed card '{card}'"
            )

        for cycle in self.supercycles:
            name = cycle.name
            card_dates = [self.card_dates[card] for card in cycle.cards if card in self.card_dates]
            if not card_dates:
                continue

            earliest_date = min(card_dates)
            latest_date = max(card_dates) if cycle.finished else today

            total_days = (latest_date - earliest_date).days
            status = "Finished" if cycle.finished else "Unfinished"
            formatted_time = format_time_difference(earliest_date, latest_date)

            # Collect card objects with Scryfall data for tooltips
            card_objects = []
            for card_name in cycle.cards:
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
                    "cards": ", ".join(cycle.cards),
                    "cardObjects": card_objects,
                    "time": formatted_time,
                    "startDate": earliest_date.strftime("%B %d, %Y"),
                    "endDate": latest_date.strftime("%B %d, %Y") if cycle.finished else "Ongoing",
                    "days": total_days,  # Store for sorting
                }
            )

        # Sort by actual day count in descending order
        return sorted(result, key=lambda x: x["days"], reverse=True)
