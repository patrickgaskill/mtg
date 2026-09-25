"""Helpers for feeding raw Scryfall-shaped card dicts to aggregators in tests."""

from typing import Any

from mtg.aggregators import Aggregator, AggregatorContext
from mtg.card import Card
from mtg.pipeline import process_cards
from mtg.rules import TypeLists


def feed(aggregator: Aggregator, *raw_cards: dict[str, Any]) -> None:
    """Pass cards to an aggregator the way the pipeline does, filtering included."""
    process_cards(raw_cards, [aggregator], aggregator.context.type_lists, max_errors=1)


def to_card(raw: dict[str, Any]) -> Card:
    return Card.from_scryfall(raw)


def type_context(creature=(), land=(), **kwargs) -> AggregatorContext:
    return AggregatorContext(
        type_lists=TypeLists(creature=frozenset(creature), land=frozenset(land)), **kwargs
    )
