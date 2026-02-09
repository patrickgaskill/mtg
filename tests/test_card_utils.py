"""Tests for card_utils.py utility functions."""

from datetime import date, datetime

import card_utils


class TestExtractTypes:
    """Tests for extract_types function."""

    def test_normal_creature_types(self):
        """Test extraction of normal creature types."""
        card = {"type_line": "Creature — Human Wizard"}
        result = card_utils.extract_types(card)
        assert result == {"Creature", "Human", "Wizard"}

    def test_time_lord_special_handling(self):
        """Test that 'Time Lord' is preserved as two words."""
        card = {"type_line": "Creature — Time Lord"}
        result = card_utils.extract_types(card)
        assert "Time Lord" in result
        assert "Time" not in result
        assert "Lord" not in result

    def test_empty_type_line(self):
        """Test handling of missing or empty type line."""
        card = {"type_line": ""}
        result = card_utils.extract_types(card)
        assert result == set()

    def test_missing_type_line(self):
        """Test handling of card without type_line field."""
        card = {}
        result = card_utils.extract_types(card)
        assert result == set()

    def test_multi_faced_card_types(self):
        """Test extraction from multi-faced card type line."""
        card = {"type_line": "Creature — Human Wizard // Creature — Human Insect"}
        result = card_utils.extract_types(card)
        assert "Human" in result
        assert "Wizard" in result
        assert "Insect" in result

    def test_hyphenated_types(self):
        """Test extraction of hyphenated types."""
        card = {"type_line": "Land — Urza's Power-Plant"}
        result = card_utils.extract_types(card)
        assert "Urza's" in result
        assert "Power-Plant" in result

    def test_artifact_equipment(self):
        """Test extraction from artifact equipment."""
        card = {"type_line": "Artifact — Equipment"}
        result = card_utils.extract_types(card)
        assert result == {"Artifact", "Equipment"}

    def test_legendary_planeswalker(self):
        """Test extraction from legendary planeswalker."""
        card = {"type_line": "Legendary Planeswalker — Jace"}
        result = card_utils.extract_types(card)
        assert result == {"Legendary", "Planeswalker", "Jace"}


class TestGetSortKey:
    """Tests for get_sort_key function."""

    def test_normal_card_sorting(self):
        """Test sort key generation for normal card."""
        card = {
            "released_at": "2023-09-08",
            "set": "woe",
            "collector_number": "123",
        }
        result = card_utils.get_sort_key(card)
        assert result == (date(2023, 9, 8), "woe", 123, "123")

    def test_collector_number_with_letters(self):
        """Test handling of collector numbers with letters (e.g., '123a')."""
        card = {
            "released_at": "2023-09-08",
            "set": "woe",
            "collector_number": "123a",
        }
        result = card_utils.get_sort_key(card)
        assert result == (date(2023, 9, 8), "woe", 123, "123a")

    def test_missing_release_date(self):
        """Test handling of card without release date."""
        card = {"set": "woe", "collector_number": "123"}
        result = card_utils.get_sort_key(card)
        assert result == (datetime.max.date(), "woe", 123, "123")

    def test_missing_collector_number(self):
        """Test handling of missing collector number."""
        card = {"released_at": "2023-09-08", "set": "woe"}
        result = card_utils.get_sort_key(card)
        assert result == (date(2023, 9, 8), "woe", 0, "")

    def test_non_numeric_collector_number(self):
        """Test handling of completely non-numeric collector number."""
        card = {
            "released_at": "2023-09-08",
            "set": "woe",
            "collector_number": "abc",
        }
        result = card_utils.get_sort_key(card)
        assert result == (date(2023, 9, 8), "woe", 0, "abc")

    def test_sorting_order(self):
        """Test that sort keys produce correct ordering."""
        card1 = {
            "released_at": "2023-09-08",
            "set": "woe",
            "collector_number": "123",
        }
        card2 = {
            "released_at": "2023-09-08",
            "set": "woe",
            "collector_number": "124",
        }
        key1 = card_utils.get_sort_key(card1)
        key2 = card_utils.get_sort_key(card2)
        assert key1 < key2


class TestIsAllCreatureTypes:
    """Tests for is_all_creature_types function."""

    def test_mistform_ultimus_special_case(self):
        """Test that Mistform Ultimus is recognized as all creature types."""
        card = {"name": "Mistform Ultimus"}
        assert card_utils.is_all_creature_types(card) is True

    def test_changeling_keyword(self):
        """Test that cards with Changeling keyword have all creature types."""
        card = {"name": "Shapesharer", "keywords": ["Changeling"]}
        assert card_utils.is_all_creature_types(card) is True

    def test_regular_creature(self):
        """Test that regular creatures don't have all creature types."""
        card = {"name": "Grizzly Bears", "keywords": []}
        assert card_utils.is_all_creature_types(card) is False


class TestIsPermanent:
    """Tests for is_permanent function."""

    def test_artifact(self):
        """Test that artifact is recognized as permanent."""
        card = {"type_line": "Artifact"}
        assert card_utils.is_permanent(card) is True

    def test_creature(self):
        """Test that creature is recognized as permanent."""
        card = {"type_line": "Creature — Human"}
        assert card_utils.is_permanent(card) is True

    def test_instant(self):
        """Test that instant is not recognized as permanent."""
        card = {"type_line": "Instant"}
        assert card_utils.is_permanent(card) is False

    def test_sorcery(self):
        """Test that sorcery is not recognized as permanent."""
        card = {"type_line": "Sorcery"}
        assert card_utils.is_permanent(card) is False

    def test_planeswalker(self):
        """Test that planeswalker is recognized as permanent."""
        card = {"type_line": "Legendary Planeswalker — Jace"}
        assert card_utils.is_permanent(card) is True

    def test_enchantment(self):
        """Test that enchantment is recognized as permanent."""
        card = {"type_line": "Enchantment"}
        assert card_utils.is_permanent(card) is True

    def test_land(self):
        """Test that land is recognized as permanent."""
        card = {"type_line": "Land"}
        assert card_utils.is_permanent(card) is True


class TestIsTraditionalCard:
    """Tests for is_traditional_card function."""

    def test_traditional_card(self):
        """Test that normal cards are recognized as traditional."""
        card = {
            "set_type": "expansion",
            "layout": "normal",
            "set": "woe",
            "border_color": "black",
        }
        assert card_utils.is_traditional_card(card) is True

    def test_non_traditional_set_type(self):
        """Test that non-traditional set types are filtered."""
        card = {
            "set_type": "memorabilia",
            "layout": "normal",
            "set": "woe",
            "border_color": "black",
        }
        assert card_utils.is_traditional_card(card) is False

    def test_non_traditional_layout(self):
        """Test that non-traditional layouts are filtered."""
        card = {
            "set_type": "expansion",
            "layout": "token",
            "set": "woe",
            "border_color": "black",
        }
        assert card_utils.is_traditional_card(card) is False

    def test_past_set_excluded(self):
        """Test that 'past' set is excluded."""
        card = {
            "set_type": "expansion",
            "layout": "normal",
            "set": "past",
            "border_color": "black",
        }
        assert card_utils.is_traditional_card(card) is False

    def test_non_traditional_border(self):
        """Test that non-traditional borders are filtered."""
        card = {
            "set_type": "expansion",
            "layout": "normal",
            "set": "woe",
            "border_color": "silver",
        }
        assert card_utils.is_traditional_card(card) is False

    def test_custom_exclusion_sets(self):
        """Test that custom exclusion sets can be provided."""
        card = {
            "set_type": "expansion",
            "layout": "normal",
            "set": "woe",
            "border_color": "black",
        }
        custom_set_types = {"expansion"}
        assert (
            card_utils.is_traditional_card(card, non_traditional_set_types=custom_set_types)
            is False
        )


class TestGeneralizeManaCost:
    """Tests for generalize_mana_cost function."""

    def test_generic_mana(self):
        """Test that generic mana is not changed."""
        assert card_utils.generalize_mana_cost("{2}") == "{2}"

    def test_repeated_single_color(self):
        """Test that repeated single color is generalized."""
        assert card_utils.generalize_mana_cost("{W}{W}") == "{M}{M}"

    def test_three_different_colors(self):
        """Test that three different colors are generalized."""
        assert card_utils.generalize_mana_cost("{W}{U}{R}") == "{M}{N}{O}"

    def test_five_colors_returns_original(self):
        """Test that five color cards return original mana cost."""
        assert card_utils.generalize_mana_cost("{W}{U}{B}{R}{G}") == "{W}{U}{B}{R}{G}"

    def test_hybrid_mana(self):
        """Test that hybrid mana is generalized."""
        assert card_utils.generalize_mana_cost("{2/W}{2/U}") == "{2/M}{2/N}"

    def test_phyrexian_mana(self):
        """Test that Phyrexian mana is generalized."""
        assert card_utils.generalize_mana_cost("{W/P}{W/U}{2/W}") == "{M/P}{M/N}{2/M}"

    def test_complex_mana_cost(self):
        """Test a complex mana cost with multiple elements."""
        assert card_utils.generalize_mana_cost("{3}{R}{R}") == "{3}{M}{M}"

    def test_colorless_mana(self):
        """Test colorless mana symbols."""
        assert card_utils.generalize_mana_cost("{C}") == "{C}"


class TestGetCardImageUri:
    """Tests for get_card_image_uri function."""

    def test_single_faced_card(self):
        """Test image URI extraction for single-faced card."""
        card = {
            "image_uris": {
                "small": "https://example.com/small.jpg",
                "normal": "https://example.com/normal.jpg",
                "large": "https://example.com/large.jpg",
            }
        }
        result = card_utils.get_card_image_uri(card)
        assert result == "https://example.com/normal.jpg"

    def test_double_faced_card(self):
        """Test image URI extraction for double-faced card."""
        card = {
            "card_faces": [
                {
                    "image_uris": {
                        "normal": "https://example.com/front.jpg",
                    }
                },
                {
                    "image_uris": {
                        "normal": "https://example.com/back.jpg",
                    }
                },
            ]
        }
        result = card_utils.get_card_image_uri(card)
        assert result == "https://example.com/front.jpg"

    def test_missing_image_uris(self):
        """Test handling of card without image URIs."""
        card = {"name": "Test Card"}
        result = card_utils.get_card_image_uri(card)
        assert result == ""

    def test_different_size(self):
        """Test image URI extraction with different size."""
        card = {
            "image_uris": {
                "small": "https://example.com/small.jpg",
                "large": "https://example.com/large.jpg",
            }
        }
        result = card_utils.get_card_image_uri(card, size="large")
        assert result == "https://example.com/large.jpg"

    def test_dfc_fallback_to_card_level(self):
        """Test fallback to card-level image URIs when face URIs missing."""
        card = {
            "card_faces": [{"name": "Front"}],
            "image_uris": {"normal": "https://example.com/fallback.jpg"},
        }
        result = card_utils.get_card_image_uri(card)
        assert result == "https://example.com/fallback.jpg"
