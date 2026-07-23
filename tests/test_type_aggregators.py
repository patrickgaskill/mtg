"""Tests for the maximal types aggregators."""

import pytest

from aggregators.type_aggregators import (
    MaximalPrintedTypesAggregator,
    MaximalTypesWithEffectsAggregator,
)

CREATURE_TYPES = ["Bear", "Doctor", "Human", "Illusion", "Time Lord", "Wizard"]
LAND_TYPES = ["Forest", "Gate", "Island", "Mountain", "Plains", "Swamp"]


@pytest.fixture
def type_files(temp_dir):
    """Write known creature and land type files, returning their paths."""
    creature_file = temp_dir / "all_creature_types.txt"
    creature_file.write_text("".join(f"{t}\n" for t in CREATURE_TYPES))
    land_file = temp_dir / "all_land_types.txt"
    land_file.write_text("".join(f"{t}\n" for t in LAND_TYPES))
    return creature_file, land_file


@pytest.fixture
def aggregator(type_files):
    return MaximalPrintedTypesAggregator(*type_files)


def make_card(**overrides):
    base = {
        "name": "Test Card",
        "type_line": "Creature — Human Wizard",
        "set_type": "expansion",
        "layout": "normal",
        "border_color": "black",
        "set": "tst",
        "collector_number": "1",
        "released_at": "2020-01-01",
    }
    base.update(overrides)
    return base


class TestUnknownSubtypeHandling:
    def test_known_subtypes_are_processed(self, aggregator):
        aggregator.process_card(make_card())
        assert len(aggregator.maximal_types) == 1

    def test_unknown_creature_subtype_is_skipped(self, aggregator):
        aggregator.process_card(make_card(name="New Card", type_line="Creature — Human Fremen"))
        assert len(aggregator.maximal_types) == 0
        assert any("Fremen" in w for w in aggregator.warnings)
        assert any("New Card" in w for w in aggregator.warnings)

    def test_unknown_land_subtype_is_skipped(self, aggregator):
        aggregator.process_card(make_card(type_line="Land — Sphere"))
        assert len(aggregator.maximal_types) == 0
        assert any("Sphere" in w for w in aggregator.warnings)

    def test_unknown_subtype_warned_once(self, aggregator):
        aggregator.process_card(make_card(type_line="Creature — Fremen"))
        aggregator.process_card(make_card(type_line="Creature — Fremen Wizard"))
        assert sum("Fremen" in w for w in aggregator.warnings) == 1

    def test_kindred_subtypes_are_checked(self, aggregator):
        aggregator.process_card(make_card(type_line="Kindred Instant — Fremen"))
        assert len(aggregator.maximal_types) == 0

    def test_land_creature_with_known_types_is_processed(self, aggregator):
        aggregator.process_card(make_card(type_line="Land Creature — Forest Bear"))
        assert len(aggregator.maximal_types) == 1

    def test_time_lord_subtype_is_recognized(self, aggregator):
        aggregator.process_card(make_card(type_line="Creature — Time Lord Doctor"))
        assert len(aggregator.maximal_types) == 1

    def test_non_creature_subtypes_are_not_checked(self, aggregator):
        # Aura is not in the creature or land type lists, but spell subtypes
        # can't be verified against the comprehensive rules type lists.
        aggregator.process_card(make_card(type_line="Enchantment — Aura"))
        assert len(aggregator.maximal_types) == 1

    def test_subtypeless_type_line_is_processed(self, aggregator):
        aggregator.process_card(make_card(type_line="Creature"))
        assert len(aggregator.maximal_types) == 1

    def test_unknown_subtype_on_card_face_is_skipped(self, aggregator):
        card = make_card(
            type_line="Creature — Human // Creature — Human Fremen",
            card_faces=[
                {"name": "Front", "type_line": "Creature — Human"},
                {"name": "Back", "type_line": "Creature — Human Fremen"},
            ],
        )
        aggregator.process_card(card)
        assert list(aggregator.maximal_types) == [("Creature", "Human")]

    def test_check_disabled_when_type_files_missing(self, temp_dir):
        aggregator = MaximalPrintedTypesAggregator(
            temp_dir / "missing_creatures.txt", temp_dir / "missing_lands.txt"
        )
        aggregator.process_card(make_card(type_line="Creature — Human Fremen"))
        assert len(aggregator.maximal_types) == 1

    def test_changeling_with_unknown_subtype_is_skipped(self, aggregator, type_files):
        aggregator.process_card(make_card(type_line="Creature — Fremen", keywords=["Changeling"]))
        assert len(aggregator.maximal_types) == 0

    def test_effects_aggregator_also_skips_unknown_subtypes(self, type_files):
        aggregator = MaximalTypesWithEffectsAggregator(*type_files)
        aggregator.process_card(make_card(type_line="Creature — Fremen"))
        assert len(aggregator.maximal_types) == 0


class TestGlobalEffects:
    def test_ashaya_makes_creatures_forest_lands(self, type_files):
        aggregator = MaximalTypesWithEffectsAggregator(*type_files)
        aggregator.process_card(make_card(type_line="Creature — Bear"))
        (key,) = aggregator.maximal_types
        assert {"Land", "Forest"}.issubset(key)

    def test_ashaya_chains_into_land_type_effects(self, type_files):
        # Ashaya grants Land before Prismatic Omen and Omo apply, so a
        # creature ends up with every land type.
        aggregator = MaximalTypesWithEffectsAggregator(*type_files)
        aggregator.process_card(make_card(type_line="Creature — Bear"))
        (key,) = aggregator.maximal_types
        assert set(LAND_TYPES).issubset(key)

    def test_ragost_makes_artifacts_foods(self, type_files):
        aggregator = MaximalTypesWithEffectsAggregator(*type_files)
        aggregator.process_card(make_card(type_line="Artifact"))
        (key,) = aggregator.maximal_types
        assert "Food" in key

    def test_ragost_applies_after_mycosynth_lattice(self, type_files):
        # Every permanent becomes an artifact via Mycosynth Lattice, so
        # Ragost grants Food to non-artifact permanents too.
        aggregator = MaximalTypesWithEffectsAggregator(*type_files)
        aggregator.process_card(make_card(type_line="Enchantment"))
        (key,) = aggregator.maximal_types
        assert "Food" in key

    def test_senator_peacock_makes_artifacts_clues(self, type_files):
        aggregator = MaximalTypesWithEffectsAggregator(*type_files)
        aggregator.process_card(make_card(type_line="Artifact"))
        (key,) = aggregator.maximal_types
        assert "Clue" in key

    def test_armed_with_proof_chains_clues_into_equipment(self, type_files):
        # Senator Peacock makes artifacts Clues, then Armed with Proof
        # makes Clues Equipment.
        aggregator = MaximalTypesWithEffectsAggregator(*type_files)
        aggregator.process_card(make_card(type_line="Artifact"))
        (key,) = aggregator.maximal_types
        assert "Equipment" in key

    def test_ashaya_ignores_noncreatures(self, type_files):
        aggregator = MaximalTypesWithEffectsAggregator(*type_files)
        aggregator.process_card(make_card(type_line="Instant"))
        (key,) = aggregator.maximal_types
        assert "Land" not in key


class TestMaximality:
    def test_subset_is_replaced_by_superset(self, aggregator):
        aggregator.process_card(make_card(type_line="Creature — Human"))
        aggregator.process_card(make_card(type_line="Creature — Human Wizard"))
        assert list(aggregator.maximal_types) == [("Creature", "Human", "Wizard")]

    def test_incomparable_sets_are_both_kept(self, aggregator):
        aggregator.process_card(make_card(type_line="Creature — Human Wizard"))
        aggregator.process_card(make_card(type_line="Creature — Bear"))
        assert len(aggregator.maximal_types) == 2
