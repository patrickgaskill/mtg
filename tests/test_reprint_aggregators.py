"""Tests for the FunctionalReprintsAggregator."""

from aggregators.reprint_aggregators import (
    FunctionalReprintsAggregator,
    _functional_signature,
    _normalize_oracle_text,
)


def make_card(**overrides):
    base = {
        "set_type": "expansion",
        "layout": "normal",
        "border_color": "black",
        "set": "tst",
        "collector_number": "1",
        "released_at": "2000-01-01",
        "colors": [],
        "scryfall_uri": "https://scryfall.com/card/tst/1",
        "image_uris": {"normal": "https://example.com/img.jpg"},
    }
    base.update(overrides)
    return base


class TestNormalizeOracleText:
    def test_replaces_card_name(self):
        assert (
            _normalize_oracle_text("Lightning Bolt deals 3 damage.", "Lightning Bolt")
            == "~ deals 3 damage."
        )

    def test_handles_missing_text(self):
        assert _normalize_oracle_text(None, "Foo") == ""
        assert _normalize_oracle_text("", "Foo") == ""

    def test_handles_missing_name(self):
        assert _normalize_oracle_text("Some text", None) == "Some text"

    def test_replaces_all_occurrences(self):
        result = _normalize_oracle_text("Foo does foo things. Foo!", "Foo")
        assert result == "~ does foo things. ~!"


class TestFunctionalSignature:
    def test_same_signature_for_functional_reprints(self):
        llanowar = make_card(
            name="Llanowar Elves",
            mana_cost="{G}",
            oracle_text="{T}: Add {G}.",
            power="1",
            toughness="1",
            colors=["G"],
            type_line="Creature — Elf Druid",
        )
        fyndhorn = make_card(
            name="Fyndhorn Elves",
            mana_cost="{G}",
            oracle_text="{T}: Add {G}.",
            power="1",
            toughness="1",
            colors=["G"],
            type_line="Creature — Elf Druid",
        )
        assert _functional_signature(llanowar) == _functional_signature(fyndhorn)

    def test_type_line_does_not_affect_signature(self):
        a = make_card(
            name="A",
            mana_cost="{G}",
            oracle_text="{T}: Add {G}.",
            power="1",
            toughness="1",
            colors=["G"],
            type_line="Creature — Elf",
        )
        b = make_card(
            name="B",
            mana_cost="{G}",
            oracle_text="{T}: Add {G}.",
            power="1",
            toughness="1",
            colors=["G"],
            type_line="Creature — Bird",
        )
        assert _functional_signature(a) == _functional_signature(b)

    def test_name_in_oracle_text_normalized(self):
        a = make_card(
            name="Foo",
            mana_cost="{R}",
            oracle_text="Foo deals 3 damage to any target.",
            colors=["R"],
        )
        b = make_card(
            name="Bar",
            mana_cost="{R}",
            oracle_text="Bar deals 3 damage to any target.",
            colors=["R"],
        )
        assert _functional_signature(a) == _functional_signature(b)

    def test_different_mana_cost_different_signature(self):
        a = make_card(name="A", mana_cost="{G}", oracle_text="{T}: Add {G}.", colors=["G"])
        b = make_card(name="B", mana_cost="{1}{G}", oracle_text="{T}: Add {G}.", colors=["G"])
        assert _functional_signature(a) != _functional_signature(b)

    def test_different_oracle_text_different_signature(self):
        a = make_card(name="A", mana_cost="{R}", oracle_text="Deal 3 damage.", colors=["R"])
        b = make_card(name="B", mana_cost="{R}", oracle_text="Deal 2 damage.", colors=["R"])
        assert _functional_signature(a) != _functional_signature(b)

    def test_different_power_toughness_different_signature(self):
        a = make_card(name="A", mana_cost="{G}", power="1", toughness="1", colors=["G"])
        b = make_card(name="B", mana_cost="{G}", power="2", toughness="2", colors=["G"])
        assert _functional_signature(a) != _functional_signature(b)

    def test_multi_face_signature(self):
        a = make_card(
            name="A // B",
            layout="split",
            card_faces=[
                {"name": "A", "mana_cost": "{R}", "oracle_text": "A deals 2.", "colors": ["R"]},
                {
                    "name": "B",
                    "mana_cost": "{U}",
                    "oracle_text": "B draws a card.",
                    "colors": ["U"],
                },
            ],
        )
        b = make_card(
            name="C // D",
            layout="split",
            card_faces=[
                {"name": "C", "mana_cost": "{R}", "oracle_text": "C deals 2.", "colors": ["R"]},
                {
                    "name": "D",
                    "mana_cost": "{U}",
                    "oracle_text": "D draws a card.",
                    "colors": ["U"],
                },
            ],
        )
        assert _functional_signature(a) == _functional_signature(b)

    def test_multi_face_does_not_match_single_face(self):
        a = make_card(name="A", mana_cost="{R}", oracle_text="Deal 2.", colors=["R"])
        b = make_card(
            name="B // C",
            layout="split",
            card_faces=[
                {"name": "B", "mana_cost": "{R}", "oracle_text": "B deals 2.", "colors": ["R"]},
                {
                    "name": "C",
                    "mana_cost": "{U}",
                    "oracle_text": "C draws a card.",
                    "colors": ["U"],
                },
            ],
        )
        assert _functional_signature(a) != _functional_signature(b)


class TestFunctionalReprintsAggregator:
    def test_groups_functional_reprints(self):
        agg = FunctionalReprintsAggregator()
        llanowar = make_card(
            name="Llanowar Elves",
            mana_cost="{G}",
            oracle_text="{T}: Add {G}.",
            power="1",
            toughness="1",
            colors=["G"],
            type_line="Creature — Elf Druid",
            set="lea",
            released_at="1993-08-05",
        )
        fyndhorn = make_card(
            name="Fyndhorn Elves",
            mana_cost="{G}",
            oracle_text="{T}: Add {G}.",
            power="1",
            toughness="1",
            colors=["G"],
            type_line="Creature — Elf Druid",
            set="ice",
            released_at="1995-06-01",
        )
        agg.process_card(llanowar)
        agg.process_card(fyndhorn)

        data = agg.get_sorted_data()
        assert len(data) == 1
        row = data[0]
        assert row["name"] == "Llanowar Elves"
        assert row["count"] == 1
        assert row["reprints"] == "Fyndhorn Elves"
        assert row["reprintObjects"][0]["name"] == "Fyndhorn Elves"

    def test_excludes_basic_lands(self):
        agg = FunctionalReprintsAggregator()
        forest = make_card(
            name="Forest",
            type_line="Basic Land — Forest",
            oracle_text="({T}: Add {G}.)",
        )
        snow_forest = make_card(
            name="Snow-Covered Forest",
            type_line="Basic Snow Land — Forest",
            oracle_text="({T}: Add {G}.)",
        )
        agg.process_card(forest)
        agg.process_card(snow_forest)
        assert agg.get_sorted_data() == []

    def test_excludes_non_traditional_cards(self):
        agg = FunctionalReprintsAggregator()
        silver = make_card(
            name="Silly Card",
            mana_cost="{G}",
            oracle_text="{T}: Add {G}.",
            colors=["G"],
            border_color="silver",
        )
        normal = make_card(
            name="Regular Card",
            mana_cost="{G}",
            oracle_text="{T}: Add {G}.",
            colors=["G"],
        )
        agg.process_card(silver)
        agg.process_card(normal)
        assert agg.get_sorted_data() == []

    def test_does_not_count_same_name_as_reprint(self):
        agg = FunctionalReprintsAggregator()
        early = make_card(
            name="Llanowar Elves",
            mana_cost="{G}",
            oracle_text="{T}: Add {G}.",
            colors=["G"],
            set="lea",
            released_at="1993-08-05",
        )
        late = make_card(
            name="Llanowar Elves",
            mana_cost="{G}",
            oracle_text="{T}: Add {G}.",
            colors=["G"],
            set="m21",
            released_at="2020-07-03",
        )
        agg.process_card(early)
        agg.process_card(late)
        assert agg.get_sorted_data() == []

    def test_original_is_earliest_printing(self):
        agg = FunctionalReprintsAggregator()
        a = make_card(
            name="A",
            mana_cost="{R}",
            oracle_text="Deal 3 damage.",
            colors=["R"],
            released_at="2010-01-01",
        )
        b = make_card(
            name="B",
            mana_cost="{R}",
            oracle_text="Deal 3 damage.",
            colors=["R"],
            released_at="1995-01-01",
        )
        c = make_card(
            name="C",
            mana_cost="{R}",
            oracle_text="Deal 3 damage.",
            colors=["R"],
            released_at="2020-01-01",
        )
        agg.process_card(a)
        agg.process_card(b)
        agg.process_card(c)

        data = agg.get_sorted_data()
        assert len(data) == 1
        row = data[0]
        assert row["name"] == "B"
        assert row["count"] == 2
        assert [r["name"] for r in row["reprintObjects"]] == ["A", "C"]

    def test_sorted_by_count_desc(self):
        agg = FunctionalReprintsAggregator()
        # First group: 1 original + 2 reprints
        for idx, name in enumerate(["Big1", "Big2", "Big3"]):
            agg.process_card(
                make_card(
                    name=name,
                    mana_cost="{R}",
                    oracle_text="Deal 3 damage.",
                    colors=["R"],
                    released_at=f"200{idx}-01-01",
                )
            )
        # Second group: 1 original + 1 reprint
        for idx, name in enumerate(["Small1", "Small2"]):
            agg.process_card(
                make_card(
                    name=name,
                    mana_cost="{G}",
                    oracle_text="Gain 3 life.",
                    colors=["G"],
                    released_at=f"200{idx}-01-01",
                )
            )

        data = agg.get_sorted_data()
        assert [(row["name"], row["count"]) for row in data] == [
            ("Big1", 2),
            ("Small1", 1),
        ]

    def test_includes_card_link_data(self):
        agg = FunctionalReprintsAggregator()
        a = make_card(
            name="A",
            mana_cost="{R}",
            oracle_text="Deal 3 damage.",
            colors=["R"],
            released_at="1995-01-01",
            scryfall_uri="https://scryfall.com/card/lea/1",
        )
        b = make_card(
            name="B",
            mana_cost="{R}",
            oracle_text="Deal 3 damage.",
            colors=["R"],
            released_at="2010-01-01",
            scryfall_uri="https://scryfall.com/card/m11/2",
        )
        agg.process_card(a)
        agg.process_card(b)

        data = agg.get_sorted_data()
        assert data[0]["scryfall_uri"] == "https://scryfall.com/card/lea/1"
        assert data[0]["reprintObjects"][0]["scryfall_uri"] == "https://scryfall.com/card/m11/2"
