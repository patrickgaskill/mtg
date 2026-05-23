"""Aggregators that analyze functional reprints across cards."""

import re
from collections import defaultdict
from typing import Any

from card_utils import (
    extract_types,
    get_card_link_data,
    get_sort_key,
    is_traditional_card,
)

from .base import Aggregator


def _normalize_oracle_text(text: str | None, name: str | None) -> str:
    """Replace card-name references with a placeholder so functional reprints match."""
    if not text:
        return ""
    if name:
        text = re.sub(rf"\b{re.escape(name)}\b", "~", text)
    return text


def _face_signature(face: dict[str, Any]) -> tuple:
    """Build a functional signature for a single card face."""
    return (
        face.get("mana_cost", "") or "",
        _normalize_oracle_text(face.get("oracle_text"), face.get("name")),
        face.get("power", "") or "",
        face.get("toughness", "") or "",
        face.get("loyalty", "") or "",
        face.get("defense", "") or "",
        tuple(sorted(face.get("colors") or [])),
    )


def _functional_signature(card: dict[str, Any]) -> tuple:
    """Build a functional signature for a card, excluding name and type line.

    Cards share a signature when they are mechanically identical: same mana cost,
    rules text (with name references normalized), power/toughness, loyalty,
    defense, and colors. Multi-faced cards must match face-for-face.
    """
    faces = card.get("card_faces")
    if faces:
        return ("multi", card.get("layout", ""), tuple(_face_signature(f) for f in faces))
    return ("single", _face_signature(card))


class FunctionalReprintsAggregator(Aggregator):
    """Find cards with the most functional reprints.

    A functional reprint is a newer card that is mechanically identical to an
    older card, differing only in name and possibly type line. Basic lands are
    excluded.
    """

    def __init__(self, description: str = ""):
        super().__init__(
            "most_functional_reprints",
            "Cards with the Most Functional Reprints",
            description,
            explanation=(
                "A **functional reprint** is a newer card that is mechanically identical to"
                " an older card — same mana cost, rules text, power/toughness, loyalty,"
                " defense, and colors — differing only in name and possibly the type line."
                " For example, Fyndhorn Elves is a functional reprint of Llanowar Elves."
                " The original card is listed alongside every later card that matches it."
                " Basic lands are excluded."
            ),
        )
        self.cards_by_name: dict[str, dict[str, Any]] = {}
        self.column_defs = [
            {
                "field": "name",
                "headerName": "Original",
                "width": 220,
                "cellRenderer": "cardLinkRenderer",
            },
            {
                "field": "count",
                "headerName": "Reprints",
                "width": 120,
                "type": "numericColumn",
                "sort": "desc",
            },
            {
                "field": "reprints",
                "headerName": "Functional Reprints",
                "width": 500,
                "wrapText": True,
                "autoHeight": True,
                "suppressAutoSize": True,
                "cellClass": "compact-cell",
                "cellRenderer": "cardLinkRenderer",
                "cardLinkData": "reprintObjects",
            },
        ]

    def process_card(self, card: dict[str, Any]) -> None:
        if not is_traditional_card(card):
            return

        name = card.get("name")
        if not name:
            return

        if "Basic" in extract_types(card):
            return

        existing = self.cards_by_name.get(name)
        if existing is None or get_sort_key(card) < get_sort_key(existing):
            self.cards_by_name[name] = card

    def get_sorted_data(self) -> list[dict[str, Any]]:
        groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
        for card in self.cards_by_name.values():
            groups[_functional_signature(card)].append(card)

        result = []
        for cards in groups.values():
            if len(cards) < 2:
                continue
            cards_sorted = sorted(cards, key=get_sort_key)
            original = cards_sorted[0]
            reprints = cards_sorted[1:]
            reprint_objects = [
                {"name": c.get("name", ""), **get_card_link_data(c)} for c in reprints
            ]
            result.append(
                {
                    "name": original.get("name", ""),
                    "count": len(reprints),
                    "reprints": ", ".join(c.get("name", "") for c in reprints),
                    "reprintObjects": reprint_objects,
                    **get_card_link_data(original),
                }
            )

        return sorted(result, key=lambda x: (-x["count"], x["name"]))
