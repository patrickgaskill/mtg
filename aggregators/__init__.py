"""Aggregator classes for processing MTG card data."""

from .base import Aggregator
from .count_aggregators import CountAggregator, MaxCollectorNumberBySetAggregator
from .first_card_aggregators import (
    FirstCardByGeneralizedManaCostAggregator,
    FirstCardByPowerToughnessAggregator,
)
from .metadata_aggregators import (
    CountCardIllustrationsBySetAggregator,
    FoilTypesAggregator,
    PromoTypesAggregator,
)
from .supercycle_aggregators import SupercycleTimeAggregator
from .type_aggregators import (
    MaximalPrintedTypesAggregator,
    MaximalTypesWithEffectsAggregator,
)

__all__ = [
    "Aggregator",
    "CountAggregator",
    "CountCardIllustrationsBySetAggregator",
    "FirstCardByGeneralizedManaCostAggregator",
    "FirstCardByPowerToughnessAggregator",
    "FoilTypesAggregator",
    "MaxCollectorNumberBySetAggregator",
    "MaximalPrintedTypesAggregator",
    "MaximalTypesWithEffectsAggregator",
    "PromoTypesAggregator",
    "SupercycleTimeAggregator",
]
