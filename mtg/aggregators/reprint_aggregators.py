"""Aggregators that analyze functional reprints across cards."""

import re
from collections import defaultdict
from typing import Any

from mtg.card import Card, Face

from .base import Aggregator


def _normalize_oracle_text(text: str | None, name: str | None) -> str:
    """Replace card-name references with a placeholder so functional reprints match."""
    if not text:
        return ""
    if name:
        text = re.sub(rf"\b{re.escape(name)}\b", "~", text)
    return text


def _face_signature(face: Face) -> tuple:
    """Build a functional signature for a single card face."""
    return (
        face.mana_cost,
        _normalize_oracle_text(face.oracle_text, face.name),
        face.power,
        face.toughness,
        face.loyalty,
        face.defense,
        tuple(sorted(face.colors)),
    )


def _functional_signature(card: Card) -> tuple:
    """Build a functional signature for a card, excluding name and type line.

    Cards share a signature when they are mechanically identical: same mana cost,
    rules text (with name references normalized), power/toughness, loyalty,
    defense, and colors. Multi-faced cards must match face-for-face.
    """
    if card.is_multiface:
        return ("multi", card.layout, tuple(_face_signature(f) for f in card.faces))
    return ("single", _face_signature(card.faces[0]))


class FunctionalReprintsAggregator(Aggregator):
    """Find cards with the most functional reprints.

    A functional reprint is a newer card that is mechanically identical to an
    older card, differing only in name and possibly type line. Basic lands are
    excluded.
    """

    name = "most_functional_reprints"
    display_name = "Cards with the Most Functional Reprints"
    description = "Cards with the most functional reprints"
    explanation = (
        "A **functional reprint** is a newer card that is mechanically identical to"
        " an older card: same mana cost, rules text, power/toughness, loyalty,"
        " defense, and colors, differing only in name and possibly the type line."
        " For example, Fyndhorn Elves is a functional reprint of Llanowar Elves."
        " The original card is listed alongside every later card that matches it."
        " Basic lands are excluded."
    )
    traditional_only = True
    column_defs = [
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

    def __init__(self, context=None):
        super().__init__(context)
        self.cards_by_name: dict[str, Card] = {}

    def process_card(self, card: Card) -> None:
        if not card.name or "Basic" in card.types:
            return

        existing = self.cards_by_name.get(card.name)
        if existing is None or card.sort_key < existing.sort_key:
            self.cards_by_name[card.name] = card

    def get_sorted_data(self) -> list[dict[str, Any]]:
        groups: dict[tuple, list[Card]] = defaultdict(list)
        for card in self.cards_by_name.values():
            groups[_functional_signature(card)].append(card)

        result = []
        for cards in groups.values():
            if len(cards) < 2:
                continue
            cards_sorted = sorted(cards, key=lambda c: c.sort_key)
            original = cards_sorted[0]
            reprints = cards_sorted[1:]
            reprint_objects = [{"name": c.name, **c.link()} for c in reprints]
            result.append(
                {
                    "name": original.name,
                    "count": len(reprints),
                    "reprints": ", ".join(c.name for c in reprints),
                    "reprintObjects": reprint_objects,
                    **original.link(),
                }
            )

        return sorted(result, key=lambda x: (-x["count"], x["name"]))
