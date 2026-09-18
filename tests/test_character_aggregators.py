"""Tests for the character appearance aggregators."""

import pytest
import yaml

from aggregators.character_aggregators import (
    CharacterAppearanceAggregator,
    derive_character_name,
)


def make_card(name, type_line, **overrides):
    base = {
        "name": name,
        "type_line": type_line,
        "set": "tst",
        "set_type": "expansion",
        "layout": "normal",
        "border_color": "black",
        "collector_number": "1",
        "released_at": "2000-01-01",
        "scryfall_uri": f"https://scryfall.com/card/tst/1/{name}",
        "image_uris": {"normal": f"https://example.com/{name}.jpg"},
    }
    base.update(overrides)
    return base


@pytest.fixture
def characters_file(tmp_path):
    def write(data):
        path = tmp_path / "characters.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    return write


@pytest.fixture
def aggregator(characters_file):
    def build(data=None, planeswalkers_only=False):
        return CharacterAppearanceAggregator(
            characters_file=characters_file(data or {}),
            planeswalkers_only=planeswalkers_only,
        )

    return build


class TestDeriveCharacterName:
    @pytest.mark.parametrize(
        ("card_name", "expected"),
        [
            ("Kaervek, the Spiteful", "Kaervek"),
            ("Kaervek the Merciless", "Kaervek"),
            ("Jhoira of the Ghitu", "Jhoira"),
            ("Sakashima of a Thousand Faces", "Sakashima"),
            ("Sidar Kondo of Jamuraa", "Sidar Kondo"),
            ("Tetsuo Umezawa", "Tetsuo Umezawa"),
            ("The Ur-Dragon", "The Ur-Dragon"),
        ],
    )
    def test_strips_titles(self, card_name, expected):
        assert derive_character_name(card_name) == expected

    def test_keeps_title_words_that_start_a_name(self):
        # Otherwise this would be filed under a character named "Lord".
        assert derive_character_name("Lord of Tresserhorn") == "Lord of Tresserhorn"


class TestCharacterAppearanceAggregator:
    def test_counts_legendary_creatures_by_character(self, aggregator):
        agg = aggregator()
        agg.process_card(make_card("Kaervek the Merciless", "Legendary Creature — Human Wizard"))
        agg.process_card(make_card("Kaervek, the Spiteful", "Legendary Creature — Human Wizard"))
        rows = agg.get_sorted_data()
        assert [(row["character"], row["count"]) for row in rows] == [("Kaervek", 2)]
        assert rows[0]["cards"] == "Kaervek the Merciless, Kaervek, the Spiteful"

    def test_ignores_nonlegendary_creatures_and_other_card_types(self, aggregator):
        agg = aggregator()
        agg.process_card(make_card("Urza's Rage", "Instant"))
        agg.process_card(make_card("Serra Angel", "Creature — Angel"))
        agg.process_card(make_card("Urza's Saga", "Legendary Enchantment Land — Urza's Saga"))
        assert agg.get_sorted_data() == []

    def test_counts_reprints_once_and_reports_first_printing(self, aggregator):
        agg = aggregator()
        agg.process_card(
            make_card(
                "Jhoira of the Ghitu",
                "Legendary Creature — Human Wizard",
                set="usg",
                released_at="1998-10-12",
            )
        )
        agg.process_card(
            make_card(
                "Jhoira of the Ghitu",
                "Legendary Creature — Human Wizard",
                set="tsr",
                released_at="2021-03-19",
            )
        )
        agg.process_card(
            make_card(
                "Jhoira, Weatherlight Captain",
                "Legendary Creature — Human Artificer",
                released_at="2018-04-27",
            )
        )
        (row,) = agg.get_sorted_data()
        assert row["count"] == 2
        assert row["firstCard"] == "Jhoira of the Ghitu"
        assert row["firstReleaseDate"] == "1998-10-12"
        assert row["latestCard"] == "Jhoira, Weatherlight Captain"
        assert row["latestReleaseDate"] == "2018-04-27"

    def test_uses_planeswalker_subtype(self, aggregator):
        agg = aggregator()
        agg.process_card(make_card("Jace Beleren", "Legendary Planeswalker — Jace"))
        agg.process_card(make_card("Jace, the Mind Sculptor", "Legendary Planeswalker — Jace"))
        assert [(row["character"], row["count"]) for row in agg.get_sorted_data()] == [("Jace", 2)]

    def test_counts_both_faces_of_a_transforming_card_once(self, aggregator):
        agg = aggregator()
        agg.process_card(
            make_card(
                "Jace, Vryn's Prodigy // Jace, Telepath Unbound",
                "Creature — Human Wizard // Legendary Planeswalker — Jace",
                layout="transform",
                card_faces=[
                    {"name": "Jace, Vryn's Prodigy", "type_line": "Legendary Creature — Human"},
                    {
                        "name": "Jace, Telepath Unbound",
                        "type_line": "Legendary Planeswalker — Jace",
                    },
                ],
            )
        )
        assert [(row["character"], row["count"]) for row in agg.get_sorted_data()] == [("Jace", 1)]

    def test_curated_card_overrides_the_automatic_rules(self, aggregator):
        agg = aggregator({"card_characters": {"Blind Seer": "Urza"}})
        agg.process_card(make_card("Blind Seer", "Creature — Human Spellshaper"))
        agg.process_card(make_card("Urza, Lord High Artificer", "Legendary Creature — Human"))
        (row,) = agg.get_sorted_data()
        assert row["character"] == "Urza"
        assert row["cards"] == "Blind Seer, Urza, Lord High Artificer"

    def test_curated_card_can_represent_two_characters(self, aggregator):
        agg = aggregator({"card_characters": {"Gisa and Geralf": ["Gisa", "Geralf"]}})
        agg.process_card(make_card("Gisa and Geralf", "Legendary Creature — Human Wizard"))
        assert [(row["character"], row["count"]) for row in agg.get_sorted_data()] == [
            ("Geralf", 1),
            ("Gisa", 1),
        ]

    def test_character_names_merge_derived_names(self, aggregator):
        agg = aggregator({"character_names": {"Bolas": "Nicol Bolas"}})
        agg.process_card(make_card("Nicol Bolas, Planeswalker", "Legendary Planeswalker — Bolas"))
        agg.process_card(make_card("Nicol Bolas, Dragon-God", "Legendary Creature — Elder Dragon"))
        assert [(row["character"], row["count"]) for row in agg.get_sorted_data()] == [
            ("Nicol Bolas", 2)
        ]

    def test_non_character_cards_are_excluded(self, aggregator):
        agg = aggregator({"non_character_cards": ["Brothers Yamazaki"]})
        agg.process_card(make_card("Brothers Yamazaki", "Legendary Creature — Human Samurai"))
        assert agg.get_sorted_data() == []

    def test_skips_non_traditional_and_rebalanced_cards(self, aggregator):
        agg = aggregator()
        agg.process_card(
            make_card(
                "Urza, Academy Headmaster",
                "Legendary Planeswalker — Urza",
                set_type="funny",
                border_color="silver",
            )
        )
        agg.process_card(
            make_card("A-Jace, the Mind Sculptor", "Legendary Planeswalker — Jace", digital=True)
        )
        assert agg.get_sorted_data() == []

    def test_sorts_by_count_then_name(self, aggregator):
        agg = aggregator()
        agg.process_card(make_card("Teferi, Timeless Voyager", "Legendary Planeswalker — Teferi"))
        agg.process_card(make_card("Teferi, Hero of Dominaria", "Legendary Planeswalker — Teferi"))
        agg.process_card(make_card("Ajani Goldmane", "Legendary Planeswalker — Ajani"))
        agg.process_card(make_card("Bolas's Citadel", "Legendary Artifact"))
        agg.process_card(make_card("Chandra Nalaar", "Legendary Planeswalker — Chandra"))
        assert [row["character"] for row in agg.get_sorted_data()] == [
            "Teferi",
            "Ajani",
            "Chandra",
        ]

    def test_card_objects_carry_scryfall_links(self, aggregator):
        agg = aggregator()
        agg.process_card(make_card("Ajani Goldmane", "Legendary Planeswalker — Ajani"))
        (row,) = agg.get_sorted_data()
        assert row["cardObjects"] == [
            {
                "name": "Ajani Goldmane",
                "scryfall_uri": "https://scryfall.com/card/tst/1/Ajani Goldmane",
                "image_uri": "https://example.com/Ajani Goldmane.jpg",
            }
        ]

    def test_warns_about_curated_entries_that_never_matched(self, aggregator):
        agg = aggregator(
            {
                "card_characters": {"Blind Seer": "Urza", "Nonexistent Card": "Urza"},
                "character_names": {"Bolas": "Nicol Bolas"},
                "non_character_cards": ["Another Missing Card"],
            }
        )
        agg.process_card(make_card("Blind Seer", "Creature — Human Spellshaper"))
        agg.get_sorted_data()
        agg.get_sorted_data()
        assert agg.warnings == [
            "characters.yaml maps card 'Nonexistent Card' to a character,"
            " but no such card was found",
            "characters.yaml excludes card 'Another Missing Card', but no such card was found",
            "characters.yaml renames character 'Bolas', but no card produced that name",
        ]

    def test_planeswalker_without_a_subtype_falls_back_to_its_name(self, aggregator):
        agg = aggregator()
        agg.process_card(make_card("Dakkon, Shadow Slayer", "Legendary Planeswalker"))
        assert [row["character"] for row in agg.get_sorted_data()] == ["Dakkon"]

    def test_unparsable_characters_file_warns_instead_of_raising(self, tmp_path):
        path = tmp_path / "characters.yaml"
        path.write_text("card_characters: [unclosed", encoding="utf-8")
        agg = CharacterAppearanceAggregator(characters_file=path)
        assert len(agg.warnings) == 1
        assert "Failed to parse character data file" in agg.warnings[0]

    def test_missing_characters_file_warns_instead_of_raising(self, tmp_path):
        agg = CharacterAppearanceAggregator(characters_file=tmp_path / "missing.yaml")
        agg.process_card(make_card("Ajani Goldmane", "Legendary Planeswalker — Ajani"))
        assert len(agg.warnings) == 1
        assert "Failed to load character data" in agg.warnings[0]
        assert [row["character"] for row in agg.get_sorted_data()] == ["Ajani"]


class TestPlaneswalkerAppearances:
    def test_only_includes_characters_with_planeswalker_cards(self, aggregator):
        agg = aggregator(planeswalkers_only=True)
        agg.process_card(make_card("Jace Beleren", "Legendary Planeswalker — Jace"))
        agg.process_card(make_card("Jace, Vryn's Prodigy", "Legendary Creature — Human Wizard"))
        agg.process_card(make_card("Kaervek the Merciless", "Legendary Creature — Human Wizard"))
        assert [(row["character"], row["count"]) for row in agg.get_sorted_data()] == [("Jace", 2)]

    def test_curated_planeswalkers_without_planeswalker_cards(self, aggregator):
        agg = aggregator({"planeswalker_characters": ["Kaervek"]}, planeswalkers_only=True)
        agg.process_card(make_card("Kaervek the Merciless", "Legendary Creature — Human Wizard"))
        assert [row["character"] for row in agg.get_sorted_data()] == ["Kaervek"]

    def test_curated_card_does_not_make_a_companion_a_planeswalker(self, aggregator):
        # "Wrenn and Six" is a Wrenn planeswalker card; Six is not a planeswalker.
        agg = aggregator(
            {"card_characters": {"Wrenn and Six": ["Wrenn", "Six"]}}, planeswalkers_only=True
        )
        agg.process_card(make_card("Wrenn and Six", "Legendary Planeswalker — Wrenn"))
        assert [row["character"] for row in agg.get_sorted_data()] == ["Wrenn"]
