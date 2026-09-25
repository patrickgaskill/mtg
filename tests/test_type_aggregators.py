"""Tests for the maximal types aggregators."""

import pytest

from mtg.aggregators.type_aggregators import (
    MaximalPrintedTypesAggregator,
    MaximalTypesWithEffectsAggregator,
)
from tests.helpers import feed, type_context

CREATURE_TYPES = ["Bear", "Doctor", "Human", "Illusion", "Time Lord", "Wizard"]
LAND_TYPES = ["Forest", "Gate", "Island", "Mountain", "Plains", "Swamp"]


@pytest.fixture
def context():
    return type_context(CREATURE_TYPES, LAND_TYPES)


@pytest.fixture
def aggregator(context):
    return MaximalPrintedTypesAggregator(context)


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
        feed(aggregator, make_card())
        assert len(aggregator.maximal_types) == 1

    def test_unknown_creature_subtype_is_skipped(self, aggregator):
        feed(aggregator, make_card(name="New Card", type_line="Creature — Human Fremen"))
        assert len(aggregator.maximal_types) == 0
        assert any("Fremen" in w for w in aggregator.warnings)
        assert any("New Card" in w for w in aggregator.warnings)

    def test_unknown_land_subtype_is_skipped(self, aggregator):
        feed(aggregator, make_card(type_line="Land — Sphere"))
        assert len(aggregator.maximal_types) == 0
        assert any("Sphere" in w for w in aggregator.warnings)

    def test_unknown_subtype_warned_once(self, aggregator):
        feed(aggregator, make_card(type_line="Creature — Fremen"))
        feed(aggregator, make_card(type_line="Creature — Fremen Wizard"))
        assert sum("Fremen" in w for w in aggregator.warnings) == 1

    def test_kindred_subtypes_are_checked(self, aggregator):
        feed(aggregator, make_card(type_line="Kindred Instant — Fremen"))
        assert len(aggregator.maximal_types) == 0

    def test_land_creature_with_known_types_is_processed(self, aggregator):
        feed(aggregator, make_card(type_line="Land Creature — Forest Bear"))
        assert len(aggregator.maximal_types) == 1

    def test_time_lord_subtype_is_recognized(self, aggregator):
        feed(aggregator, make_card(type_line="Creature — Time Lord Doctor"))
        assert len(aggregator.maximal_types) == 1

    def test_non_creature_subtypes_are_not_checked(self, aggregator):
        # Aura is not in the creature or land type lists, but spell subtypes
        # can't be verified against the comprehensive rules type lists.
        feed(aggregator, make_card(type_line="Enchantment — Aura"))
        assert len(aggregator.maximal_types) == 1

    def test_subtypeless_type_line_is_processed(self, aggregator):
        feed(aggregator, make_card(type_line="Creature"))
        assert len(aggregator.maximal_types) == 1

    def test_unknown_subtype_on_card_face_is_skipped(self, aggregator):
        card = make_card(
            type_line="Creature — Human // Creature — Human Fremen",
            card_faces=[
                {"name": "Front", "type_line": "Creature — Human"},
                {"name": "Back", "type_line": "Creature — Human Fremen"},
            ],
        )
        feed(aggregator, card)
        assert list(aggregator.maximal_types) == [frozenset({"Creature", "Human"})]

    def test_check_disabled_when_type_lists_missing(self):
        aggregator = MaximalPrintedTypesAggregator()
        feed(aggregator, make_card(type_line="Creature — Human Fremen"))
        assert len(aggregator.maximal_types) == 1
        assert any("update-types" in w for w in aggregator.warnings)

    def test_changeling_with_unknown_subtype_is_skipped(self, aggregator):
        feed(aggregator, make_card(type_line="Creature — Fremen", keywords=["Changeling"]))
        assert len(aggregator.maximal_types) == 0

    def test_effects_aggregator_also_skips_unknown_subtypes(self, context):
        aggregator = MaximalTypesWithEffectsAggregator(context)
        feed(aggregator, make_card(type_line="Creature — Fremen"))
        assert len(aggregator.maximal_types) == 0


class TestGlobalEffects:
    def test_ashaya_makes_creatures_forest_lands(self, context):
        aggregator = MaximalTypesWithEffectsAggregator(context)
        feed(aggregator, make_card(type_line="Creature — Bear"))
        (key,) = aggregator.maximal_types
        assert {"Land", "Forest"}.issubset(key)

    def test_ashaya_chains_into_land_type_effects(self, context):
        # Ashaya grants Land before Omo applies, so a creature ends up
        # with every land type.
        aggregator = MaximalTypesWithEffectsAggregator(context)
        feed(aggregator, make_card(type_line="Creature — Bear"))
        (key,) = aggregator.maximal_types
        assert set(LAND_TYPES).issubset(key)

    def test_ragost_makes_artifacts_foods(self, context):
        aggregator = MaximalTypesWithEffectsAggregator(context)
        feed(aggregator, make_card(type_line="Artifact"))
        (key,) = aggregator.maximal_types
        assert "Food" in key

    def test_ragost_applies_after_mycosynth_lattice(self, context):
        # Every permanent becomes an artifact via Mycosynth Lattice, so
        # Ragost grants Food to non-artifact permanents too.
        aggregator = MaximalTypesWithEffectsAggregator(context)
        feed(aggregator, make_card(type_line="Enchantment"))
        (key,) = aggregator.maximal_types
        assert "Food" in key

    def test_senator_peacock_makes_artifacts_clues(self, context):
        aggregator = MaximalTypesWithEffectsAggregator(context)
        feed(aggregator, make_card(type_line="Artifact"))
        (key,) = aggregator.maximal_types
        assert "Clue" in key

    def test_armed_with_proof_chains_clues_into_equipment(self, context):
        # Senator Peacock makes artifacts Clues, then Armed with Proof
        # makes Clues Equipment.
        aggregator = MaximalTypesWithEffectsAggregator(context)
        feed(aggregator, make_card(type_line="Artifact"))
        (key,) = aggregator.maximal_types
        assert "Equipment" in key

    def test_ashaya_ignores_noncreatures(self, context):
        aggregator = MaximalTypesWithEffectsAggregator(context)
        feed(aggregator, make_card(type_line="Instant"))
        (key,) = aggregator.maximal_types
        assert "Land" not in key


class TestPlaceholderTypes:
    def test_card_placeholder_type_is_skipped(self, aggregator):
        feed(aggregator, make_card(type_line="Card"))
        assert len(aggregator.maximal_types) == 0

    def test_stickers_placeholder_type_is_skipped(self, aggregator):
        feed(aggregator, make_card(type_line="Stickers"))
        assert len(aggregator.maximal_types) == 0

    def test_card_placeholder_face_is_skipped(self, aggregator):
        card = make_card(
            type_line="Card // Creature — Human",
            card_faces=[
                {"name": "Front", "type_line": "Card"},
                {"name": "Back", "type_line": "Creature — Human"},
            ],
        )
        feed(aggregator, card)
        assert list(aggregator.maximal_types) == [frozenset({"Creature", "Human"})]

    def test_effects_aggregator_also_skips_card_placeholder(self, context):
        aggregator = MaximalTypesWithEffectsAggregator(context)
        feed(aggregator, make_card(type_line="Card"))
        assert len(aggregator.maximal_types) == 0


class TestNameBasedTypes:
    def test_grist_counts_as_insect_creature(self, aggregator):
        feed(
            aggregator,
            make_card(
                name="Grist, the Hunger Tide",
                type_line="Legendary Planeswalker — Grist",
            ),
        )
        assert list(aggregator.maximal_types) == [
            frozenset({"Creature", "Grist", "Insect", "Legendary", "Planeswalker"})
        ]

    def test_other_planeswalkers_are_unchanged(self, aggregator):
        feed(aggregator, make_card(name="Jace Beleren", type_line="Legendary Planeswalker — Jace"))
        assert list(aggregator.maximal_types) == [frozenset({"Jace", "Legendary", "Planeswalker"})]


class TestFaceImages:
    def test_maximal_back_face_uses_its_own_image(self, aggregator):
        # A row produced by the back face of a double-faced card must show
        # that face's image, not the front face's.
        card = make_card(
            name="Front Face // Back Face",
            type_line="Creature — Human // Creature — Human Wizard",
            card_faces=[
                {
                    "name": "Front Face",
                    "type_line": "Creature — Human",
                    "image_uris": {"normal": "front.jpg"},
                },
                {
                    "name": "Back Face",
                    "type_line": "Creature — Human Wizard",
                    "image_uris": {"normal": "back.jpg"},
                },
            ],
        )
        feed(aggregator, card)
        (row,) = aggregator.get_sorted_data()
        assert row["image_uri"] == "back.jpg"

    def test_single_faced_card_image_is_unchanged(self, aggregator):
        feed(aggregator, make_card(image_uris={"normal": "card.jpg"}))
        (row,) = aggregator.get_sorted_data()
        assert row["image_uri"] == "card.jpg"


class TestMaximality:
    def test_subset_is_replaced_by_superset(self, aggregator):
        feed(aggregator, make_card(type_line="Creature — Human"))
        feed(aggregator, make_card(type_line="Creature — Human Wizard"))
        assert list(aggregator.maximal_types) == [frozenset({"Creature", "Human", "Wizard"})]

    def test_incomparable_sets_are_both_kept(self, aggregator):
        feed(aggregator, make_card(type_line="Creature — Human Wizard"))
        feed(aggregator, make_card(type_line="Creature — Bear"))
        assert len(aggregator.maximal_types) == 2


class TestMixedSubtypes:
    @pytest.fixture
    def aggregator(self):
        return MaximalPrintedTypesAggregator(
            type_context(["Lizard", "Warrior"], ["Forest", "Urza's"])
        )

    @pytest.mark.parametrize(
        "type_line",
        [
            "Enchantment Land — Urza's Saga",
            "Artifact Creature — Equipment Lizard",
            "Tribal Artifact — Warrior Equipment",
        ],
    )
    def test_known_non_creature_subtypes_are_not_unknown(self, aggregator, type_line):
        feed(aggregator, make_card(type_line=type_line))
        assert len(aggregator.maximal_types) == 1
        assert aggregator.warnings == []

    def test_subset_is_replaced_by_superset(self, aggregator):
        feed(aggregator, make_card(type_line="Creature — Lizard"))
        feed(aggregator, make_card(type_line="Artifact Creature — Equipment Lizard"))
        assert list(aggregator.maximal_types) == [
            frozenset({"Artifact", "Creature", "Equipment", "Lizard"})
        ]
