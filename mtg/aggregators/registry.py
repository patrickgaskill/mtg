"""The reports to generate, in the order they're listed on the site."""

from .base import Aggregator, AggregatorContext
from .count_aggregators import (
    CardsByNameAggregator,
    CardsBySetAndNameAggregator,
    FinishesByNameAggregator,
    FinishesBySetAndNameAggregator,
    MaxCollectorNumberBySetAggregator,
)
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
from .reprint_aggregators import FunctionalReprintsAggregator
from .supercycle_aggregators import SupercycleTimeAggregator
from .type_aggregators import MaximalPrintedTypesAggregator, MaximalTypesWithEffectsAggregator

AGGREGATOR_CLASSES: list[type[Aggregator]] = [
    CardsByNameAggregator,
    FinishesByNameAggregator,
    CardsBySetAndNameAggregator,
    FinishesBySetAndNameAggregator,
    CountCardIllustrationsBySetAggregator,
    MaxCollectorNumberBySetAggregator,
    MaximalPrintedTypesAggregator,
    PromoTypesAggregator,
    FirstCardByPowerToughnessAggregator,
    FoilTypesAggregator,
    SupercycleTimeAggregator,
    MaximalTypesWithEffectsAggregator,
    FirstCardByGeneralizedManaCostAggregator,
    MostPrintingsSameArtAggregator,
    MostUniqueIllustrationsAggregator,
    FunctionalReprintsAggregator,
    CreatureTypeCountAggregator,
    FirstCardByCreatureTypeAggregator,
    CreatureTypeCombinationCountAggregator,
    FirstCreatureTypeByColorAggregator,
    FirstLegendaryByCreatureTypeAggregator,
    TokenOnlyCreatureTypesAggregator,
    RulesOnlyCreatureTypesAggregator,
]


def create_aggregators(
    context: AggregatorContext | None = None,
    only: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[Aggregator]:
    """Instantiate the registered aggregators, optionally filtered by name."""
    classes = AGGREGATOR_CLASSES
    if only:
        classes = [cls for cls in classes if cls.name in only]
    if exclude:
        classes = [cls for cls in classes if cls.name not in exclude]
    return [cls(context) for cls in classes]
