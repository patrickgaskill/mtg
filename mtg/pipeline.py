"""Run aggregators over a stream of cards."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from mtg.aggregators import Aggregator
from mtg.card import Card
from mtg.rules import TypeLists


class TooManyErrors(Exception):
    """Processing hit the error limit and stopped."""


@dataclass
class Report:
    """One aggregator's finished output."""

    aggregator: Aggregator
    rows: list[dict[str, Any]]


def load_type_lists(path: Path) -> TypeLists:
    """Load the rules type lists, or return empty lists (with a warning) if unavailable."""
    try:
        return TypeLists.load(path)
    except (OSError, ValueError, KeyError) as e:
        logger.warning("Couldn't load type lists from {}: {}. Run `mtg update-types`.", path, e)
        return TypeLists()


def process_cards(
    raw_cards: Iterable[dict[str, Any]],
    aggregators: list[Aggregator],
    type_lists: TypeLists,
    max_errors: int = 100,
) -> int:
    """Build a Card from each Scryfall object and pass it to every aggregator.

    Aggregators with `traditional_only` only see traditional cards. Errors are
    logged and counted; processing stops with TooManyErrors after `max_errors`.
    Returns the number of cards read.
    """
    all_cards = [agg for agg in aggregators if not agg.traditional_only]
    traditional_only = [agg for agg in aggregators if agg.traditional_only]
    non_creature_subtypes = type_lists.non_creature_land_subtypes
    land_types = type_lists.land_or_default

    error_count = 0
    card_count = 0

    def record_error(message: str, *args: Any) -> None:
        nonlocal error_count
        error_count += 1
        logger.error(message, *args)
        if error_count >= max_errors:
            raise TooManyErrors(f"Too many processing errors ({error_count}), aborting")

    for raw in raw_cards:
        card_count += 1
        try:
            card = Card.from_scryfall(raw, non_creature_subtypes, land_types)
        except Exception as e:
            record_error("Error reading card {}: {}", raw.get("name", "Unknown"), e)
            continue
        targets = all_cards + traditional_only if card.is_traditional else all_cards
        for aggregator in targets:
            try:
                aggregator.process_card(card)
            except Exception as e:
                record_error("Error in {} processing card {}: {}", aggregator.name, card.name, e)

    logger.debug("Processed {} cards", card_count)
    if error_count:
        logger.warning("Completed with {} processing error(s)", error_count)
    return card_count


def build_reports(aggregators: list[Aggregator]) -> list[Report]:
    """Collect each aggregator's rows, skipping (and logging) any that fail."""
    reports = []
    for aggregator in aggregators:
        try:
            reports.append(Report(aggregator, aggregator.get_sorted_data()))
        except Exception as e:
            logger.error("Error building report {}: {}", aggregator.name, e)
    return reports
