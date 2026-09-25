"""Aggregators that find the first card with specific characteristics."""

from collections.abc import Iterable
from typing import Any

from mtg.card import Card, Face
from mtg.card_utils import generalize_mana_cost

from .base import FirstCardByKeyAggregator, card_columns


class FirstCardByPowerToughnessAggregator(FirstCardByKeyAggregator):
    """Find the first card printed for each power/toughness combination."""

    name = "first_card_by_power_toughness"
    display_name = "First Cards by Power and Toughness"
    description = "First card for each unique power/toughness combination"
    traditional_only = True
    column_defs = [
        {"field": "power", "headerName": "Power", "width": 90},
        {"field": "toughness", "headerName": "Toughness", "width": 110},
        *card_columns("Name"),
    ]

    def keys(self, card: Card) -> Iterable[tuple[Any, Face | None]]:
        # Multi-faced cards usually keep power/toughness on their faces rather
        # than the card itself, so check both.
        for face in card.faces:
            if face.power and face.toughness:
                yield (face.power, face.toughness), face
        if card.is_multiface and card.power and card.toughness:
            yield (card.power, card.toughness), None

    def key_fields(self, key: tuple[str, str]) -> dict[str, Any]:
        power, toughness = key
        return {"power": power, "toughness": toughness}


class FirstCardByGeneralizedManaCostAggregator(FirstCardByKeyAggregator):
    """Find the first card printed for each generalized mana cost."""

    name = "first_card_by_generalized_mana_cost"
    display_name = "First Cards by Generalized Mana Cost"
    description = "First card for each generalized mana cost"
    column_defs = [
        {"field": "generalizedManaCost", "headerName": "Generalized Mana Cost", "width": 200},
        *card_columns("Name"),
        {"field": "originalManaCost", "headerName": "Original Mana Cost", "width": 180},
        {"field": "count", "headerName": "Count", "width": 100, "type": "numericColumn"},
    ]
    # The face only supplies the original cost; rows show the card's default image.
    image_from_face = False

    def keys(self, card: Card) -> Iterable[tuple[Any, Face | None]]:
        for face in card.faces:
            if face.mana_cost:
                yield generalize_mana_cost(face.mana_cost), face

    def key_fields(self, key: str) -> dict[str, Any]:
        return {"generalizedManaCost": key}

    def extra_fields(self, key: str, _card: Card, face: Face | None, /) -> dict[str, Any]:
        return {"originalManaCost": face.mana_cost if face else "", "count": self.counts[key]}
