"""Tests for creature type extraction and the creature type aggregators."""

import pytest

from aggregators.creature_type_aggregators import (
    CreatureTypeCountAggregator,
    RulesOnlyCreatureTypesAggregator,
    TokenOnlyCreatureTypesAggregator,
    extract_creature_subtypes,
)


def make_card(**overrides):
    base = {
        "name": "Test Card",
        "type_line": "Creature — Elf",
        "set_type": "expansion",
        "layout": "normal",
        "border_color": "black",
        "set": "tst",
        "collector_number": "1",
        "released_at": "2020-01-01",
    }
    base.update(overrides)
    return base


class TestExtractCreatureSubtypes:
    @pytest.mark.parametrize(
        ("type_line", "expected"),
        [
            ("Creature — Human Wizard", {"Human", "Wizard"}),
            ("Creature — Time Lord Human", {"Time Lord", "Human"}),
            ("Artifact Creature — Equipment Lizard", {"Lizard"}),
            ("Artifact Creature — Vehicle Construct", {"Construct"}),
            ("Kindred Instant — Elf", {"Elf"}),
            ("Tribal Artifact — Warrior Equipment", {"Warrior"}),
            ("Kindred Enchantment — Faerie Aura", {"Faerie"}),
            ("Land Creature — Forest Dryad", {"Dryad"}),
            ("Enchantment — Aura", set()),
            ("Instant", set()),
            ("Creature — Human // Creature — Human Insect", {"Human", "Insect"}),
        ],
    )
    def test_extracts_only_creature_types(self, type_line, expected):
        assert extract_creature_subtypes({"type_line": type_line}) == expected


class TestCreatureTypeCount:
    def test_kindred_cards_are_counted(self):
        aggregator = CreatureTypeCountAggregator()
        aggregator.process_card(make_card(type_line="Kindred Instant — Elf"))
        assert aggregator.counts == {"Elf": 1}

    def test_equipment_is_not_a_creature_type(self):
        aggregator = CreatureTypeCountAggregator()
        aggregator.process_card(make_card(type_line="Artifact Creature — Equipment Lizard"))
        assert aggregator.counts == {"Lizard": 1}


class TestTokenOnlyCreatureTypes:
    def test_type_on_kindred_card_is_not_token_only(self):
        aggregator = TokenOnlyCreatureTypesAggregator()
        aggregator.process_card(make_card(type_line="Token Creature — Faerie", layout="token"))
        aggregator.process_card(make_card(type_line="Kindred Sorcery — Faerie"))
        assert aggregator.get_sorted_data() == []


class TestRulesOnlyCreatureTypes:
    @pytest.fixture
    def aggregator(self, temp_dir):
        types_file = temp_dir / "all_creature_types.txt"
        types_file.write_text("Camarid\nElf\nTime Lord\n")
        return RulesOnlyCreatureTypesAggregator(types_file)

    def test_matches_whole_words_only(self, aggregator):
        aggregator.process_card(
            make_card(type_line="Instant", oracle_text="It deals damage to itself.")
        )
        assert "Elf" not in aggregator.first_text_mention

    def test_matches_plurals_and_multiword_types(self, aggregator):
        card = make_card(
            name="Mention",
            type_line="Sorcery",
            oracle_text="Create two 1/1 Camarids and a Time Lord.",
        )
        aggregator.process_card(card)
        assert set(aggregator.first_text_mention) == {"Camarid", "Time Lord"}

    def test_reports_types_never_on_a_card(self, aggregator):
        aggregator.process_card(make_card(type_line="Creature — Elf"))
        assert [row["creatureType"] for row in aggregator.get_sorted_data()] == [
            "Camarid",
            "Time Lord",
        ]
