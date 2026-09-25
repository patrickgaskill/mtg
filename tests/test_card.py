"""Tests for the normalized Card model."""

from mtg.card import Card


def make(**raw):
    base = {
        "name": "Test Card",
        "set": "tst",
        "set_type": "expansion",
        "layout": "normal",
        "border_color": "black",
        "collector_number": "1",
        "released_at": "2020-01-01",
        "type_line": "Creature — Human",
    }
    base.update(raw)
    return Card.from_scryfall(base)


class TestAllCreatureTypes:
    def test_mistform_ultimus(self):
        assert make(name="Mistform Ultimus").is_all_creature_types

    def test_changeling_keyword(self):
        assert make(keywords=["Changeling"]).is_all_creature_types
        assert make(keywords=["Changeling"]).faces[0].is_all_creature_types

    def test_regular_creature(self):
        assert not make(keywords=["Flying"]).is_all_creature_types


class TestFaces:
    def test_single_faced_card_has_one_mirror_face(self):
        card = make(power="2", toughness="3", mana_cost="{1}{G}", oracle_text="Reach")
        (face,) = card.faces
        assert not card.is_multiface
        assert (face.name, face.power, face.toughness, face.mana_cost) == (
            "Test Card",
            "2",
            "3",
            "{1}{G}",
        )

    def test_double_faced_card(self, sample_dfc_card):
        card = Card.from_scryfall(sample_dfc_card)
        front, back = card.faces
        assert card.is_multiface
        assert (back.name, back.power, back.toughness) == ("Insectile Aberration", "3", "2")
        assert card.oracle_text.endswith("Flying")
        assert card.creature_subtypes == ("Human", "Insect", "Wizard")


class TestLink:
    def test_single_faced_card(self):
        card = make(
            scryfall_uri="https://scryfall.com/card/woe/123",
            image_uris={"normal": "https://example.com/normal.jpg"},
        )
        assert card.link() == {
            "scryfall_uri": "https://scryfall.com/card/woe/123",
            "image_uri": "https://example.com/normal.jpg",
        }

    def test_missing_fields(self):
        assert Card.from_scryfall({}).link() == {"scryfall_uri": "", "image_uri": ""}

    def test_double_faced_card_defaults_to_front_image(self):
        card = make(
            scryfall_uri="https://scryfall.com/card/mid/1",
            card_faces=[
                {"name": "Front", "image_uris": {"normal": "https://example.com/front.jpg"}},
                {"name": "Back", "image_uris": {"normal": "https://example.com/back.jpg"}},
            ],
        )
        front, back = card.faces
        assert card.link()["image_uri"] == "https://example.com/front.jpg"
        assert card.link(back)["image_uri"] == "https://example.com/back.jpg"


class TestDerivedFields:
    def test_traditional_and_token(self):
        assert make().is_traditional
        token = make(layout="token", type_line="Token Creature — Germ")
        assert token.is_token
        assert not token.is_traditional

    def test_creature_subtypes_use_given_subtype_lists(self):
        card = Card.from_scryfall(
            {"type_line": "Artifact Creature — Gizmo Robot"},
            non_creature_subtypes=frozenset({"Gizmo"}),
        )
        assert card.creature_subtypes == ("Robot",)

    def test_release_date(self):
        assert make().released_date.isoformat() == "2020-01-01"
        assert Card.from_scryfall({}).released_date is None
