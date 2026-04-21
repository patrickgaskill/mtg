"""Aggregator classes for processing MTG card data."""

from .base import Aggregator
from .count_aggregators import CountAggregator, MaxCollectorNumberBySetAggregator
from .creature_type_aggregators import (
    CreatureTypeCombinationCountAggregator,
    CreatureTypeCountAggregator,
    FirstCardByCreatureTypeAggregator,
    FirstCreatureTypeByColorAggregator,
    FirstLegendaryByCreatureTypeAggregator,
    RulesOnlyCreatureTypesAggregator,
    TokenOnlyCreatureTypesAggregator,
)
from .first_card_aggregators import (
    FirstCardByGeneralizedManaCostAggregator,
    FirstCardByPowerToughnessAggregator,
)
from .metadata_aggregators import (
    CountCardIllustrationsBySetAggregator,
    FoilTypesAggregator,
    MostPrintingsSameArtAggregator,
    MostUniqueIllustrationsAggregator,
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
    "CreatureTypeCombinationCountAggregator",
    "CreatureTypeCountAggregator",
    "FirstCardByCreatureTypeAggregator",
    "FirstCardByGeneralizedManaCostAggregator",
    "FirstCardByPowerToughnessAggregator",
    "FirstCreatureTypeByColorAggregator",
    "FirstLegendaryByCreatureTypeAggregator",
    "FoilTypesAggregator",
    "MaxCollectorNumberBySetAggregator",
    "MaximalPrintedTypesAggregator",
    "MaximalTypesWithEffectsAggregator",
    "MostPrintingsSameArtAggregator",
    "MostUniqueIllustrationsAggregator",
    "PromoTypesAggregator",
    "RulesOnlyCreatureTypesAggregator",
    "SupercycleTimeAggregator",
    "TokenOnlyCreatureTypesAggregator",
]
