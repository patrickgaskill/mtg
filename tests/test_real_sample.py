"""Checks over a real Scryfall sample (tests/fixtures/scryfall_sample.jsonl.gz).

The sample and data/rules/types.json come from the "Refresh rules and test data"
workflow. Unlike the golden test, these check invariants rather than exact output,
so refreshing the sample doesn't require updating expectations. They're skipped
until the sample exists.
"""

from pathlib import Path

import pytest

from mtg.aggregators import AggregatorContext, create_aggregators
from mtg.aggregators.type_aggregators import MaximalPrintedTypesAggregator
from mtg.card import Card
from mtg.pipeline import build_reports, load_type_lists, process_cards
from mtg.scryfall import iter_cards

ROOT = Path(__file__).parent.parent
SAMPLE = Path(__file__).parent / "fixtures" / "scryfall_sample.jsonl.gz"
TYPES_FILE = ROOT / "data" / "rules" / "types.json"

pytestmark = pytest.mark.skipif(not SAMPLE.exists(), reason="real-card sample not generated yet")


@pytest.fixture(scope="module")
def raw_cards():
    return list(iter_cards(SAMPLE))


@pytest.fixture(scope="module")
def type_lists():
    if not TYPES_FILE.exists():
        pytest.skip("data/rules/types.json not generated yet")
    return load_type_lists(TYPES_FILE)


def test_every_card_parses(raw_cards):
    for raw in raw_cards:
        card = Card.from_scryfall(raw)
        assert card.faces, raw.get("name")
        assert card.name, raw.get("id")


def test_double_faced_cards_have_art_and_face_images(raw_cards):
    for raw in raw_cards:
        if raw.get("layout") in {"transform", "modal_dfc"} and raw.get("card_faces"):
            card = Card.from_scryfall(raw)
            assert card.illustration_key, card.name
            assert all(face.image_uri for face in card.faces), card.name


def test_all_reports_build_without_errors(raw_cards, type_lists):
    aggregators = create_aggregators(AggregatorContext(type_lists=type_lists))

    process_cards(raw_cards, aggregators, type_lists, max_errors=1)
    reports = build_reports(aggregators)

    assert [r.aggregator.name for r in reports] == [a.name for a in aggregators]


def test_rules_type_lists_look_complete(type_lists):
    # Guards against the parser cutting lists short again.
    assert len(type_lists.creature) > 250
    assert {"Equipment", "Vehicle", "Food", "Treasure"} <= type_lists.artifact
    assert {"Aura", "Saga", "Shrine", "Background"} <= type_lists.enchantment
    assert {"Adventure", "Arcane", "Lesson"} <= type_lists.spell
    assert not any("(" in t for t in type_lists.artifact | type_lists.enchantment)


def test_known_subtypes_are_never_reported_unknown(raw_cards, type_lists):
    aggregator = MaximalPrintedTypesAggregator(AggregatorContext(type_lists=type_lists))

    process_cards(raw_cards, [aggregator], type_lists, max_errors=1)

    known = type_lists.non_creature_land_subtypes | type_lists.creature | type_lists.land
    flagged = [w for w in aggregator.warnings if any(f"'{t}'" in w for t in known)]
    assert flagged == []
