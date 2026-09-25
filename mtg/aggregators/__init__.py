"""Aggregator classes for processing MTG card data."""

from .base import Aggregator, AggregatorContext, FirstCardByKeyAggregator
from .registry import AGGREGATOR_CLASSES, create_aggregators

__all__ = [
    "AGGREGATOR_CLASSES",
    "Aggregator",
    "AggregatorContext",
    "FirstCardByKeyAggregator",
    "create_aggregators",
]
