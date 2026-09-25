"""Base aggregator classes and shared helpers."""

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from mtg.card import Card, Face
from mtg.rules import TypeLists


@dataclass(frozen=True)
class AggregatorContext:
    """External inputs some aggregators need, supplied by the runner."""

    type_lists: TypeLists = field(default_factory=TypeLists)
    supercycles_file: Path | None = None
    today: Callable[[], date] = date.today


class Aggregator(ABC):
    """Base class for all aggregators.

    Subclasses describe their report with class attributes and implement
    `process_card` (called once per card) and `get_sorted_data` (the report rows).
    """

    name: str = ""
    display_name: str = ""
    description: str = ""
    # Markdown shown above the report grid.
    explanation: str = ""
    # When True, the runner only passes traditional cards (see Card.is_traditional).
    traditional_only: bool = False
    # AG Grid column definitions for the report.
    column_defs: list[dict[str, Any]] = []
    # Checkbox toggles that hide rows whose `field` contains `keyword` as a word.
    type_filters: list[dict[str, str]] = []

    def __init__(self, context: AggregatorContext | None = None):
        self.context = context or AggregatorContext()
        self.warnings: list[str] = []

    @abstractmethod
    def process_card(self, card: Card) -> None:
        """Process a single card."""

    @abstractmethod
    def get_sorted_data(self) -> list[dict[str, Any]]:
        """Return the report rows in display order."""


def card_columns(header: str = "First Card") -> list[dict[str, Any]]:
    """Column definitions for the card name, set, and release date of a row."""
    return [
        {"field": "name", "headerName": header, "width": 200, "cellRenderer": "cardLinkRenderer"},
        {"field": "set", "headerName": "Set", "width": 80},
        {"field": "releaseDate", "headerName": "Release Date", "width": 120},
    ]


def card_fields(card: Card, face: Face | None = None) -> dict[str, Any]:
    """Row fields matching `card_columns`, plus the link data the grid renderer uses."""
    return {
        "name": card.name,
        "set": card.set,
        "releaseDate": card.released_at,
        **card.link(face),
    }


class FirstCardByKeyAggregator(Aggregator):
    """Keep the first (or latest) printed card for each key a card produces.

    Subclasses implement `keys`, yielding each key for a card along with the face
    whose image should represent it (or None for the card's default image), and
    `key_fields`, turning a key into row fields. How many cards produced each key
    is tracked in `self.counts`.
    """

    # Keep the most recent card per key instead of the earliest.
    prefer_latest: bool = False
    # Show the yielded face's image in rows rather than the card's default image.
    image_from_face: bool = True

    def __init__(self, context: AggregatorContext | None = None):
        super().__init__(context)
        self.best: dict[Hashable, tuple[Card, Face | None]] = {}
        self.counts: dict[Hashable, int] = defaultdict(int)

    @abstractmethod
    def keys(self, card: Card) -> Iterable[tuple[Hashable, Face | None]]:
        """Yield (key, face) pairs for a card."""

    @abstractmethod
    def key_fields(self, key: Any) -> dict[str, Any]:
        """Row fields describing a key."""

    def extra_fields(self, key: Any, card: Card, face: Face | None, /) -> dict[str, Any]:  # noqa: ARG002
        """Additional row fields; override to add e.g. counts."""
        return {}

    def process_card(self, card: Card) -> None:
        for key, face in self.keys(card):
            self.counts[key] += 1
            current = self.best.get(key)
            if current is None or self._is_better(card, current[0]):
                self.best[key] = (card, face)

    def _is_better(self, card: Card, existing: Card) -> bool:
        if self.prefer_latest:
            return card.sort_key > existing.sort_key
        return card.sort_key < existing.sort_key

    def sorted_items(self) -> list[tuple[Any, tuple[Card, Face | None]]]:
        """Order of report rows; by default, by each key's card."""
        return sorted(self.best.items(), key=lambda item: item[1][0].sort_key)

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                **self.key_fields(key),
                **card_fields(card, face if self.image_from_face else None),
                **self.extra_fields(key, card, face),
            }
            for key, (card, face) in self.sorted_items()
        ]
