"""Tests for rules.py functions."""

import pytest
import responses
from requests.exceptions import ConnectionError, RequestException, Timeout

from mtg import rules

# 50+ creature types to satisfy validation threshold
SAMPLE_CREATURE_TYPES = (
    "Advisor, Aetherborn, Ally, Angel, Antelope, Ape, Archer, Archon, Army, Assassin, "
    "Assembly-Worker, Astartes, Atog, Aurochs, Avatar, Azra, Badger, Balloon, Barbarian, "
    "Bard, Basilisk, Bat, Bear, Beast, Beholder, Berserker, Bird, Blinkmoth, Boar, Bringer, "
    "Brushwagg, Camarid, Camel, Caribou, Carrier, Cat, Centaur, Cephalid, Chimera, Citizen, "
    "Cleric, Clown, Cockatrice, Construct, Coward, Crab, Crocodile, Cyclops, Dauthi, "
    "Demigod, Demon, Deserter, and Devil"
)
SAMPLE_LAND_TYPES = "Desert, Forest, Gate, Island, Lair, Locus, Mine, Mountain, Plains, Power-Plant, Swamp, Tower, and Urza's"


def make_rules_text(creature_types=SAMPLE_CREATURE_TYPES, land_types=SAMPLE_LAND_TYPES):
    """Build a mock comprehensive rules text with the given types."""
    return f"""
        Some text before...
        All other creature types are one word long: {creature_types}.
        More text...
        205.3g Artifacts have their own unique set of subtypes; these subtypes are called artifact types. The artifact types are Clue, Equipment (see rule 301.5), Food, Fortification (see rule 301.6), and Vehicle (see rule 301.7).
        205.3h Enchantments have their own unique set of subtypes; these subtypes are called enchantment types. The enchantment types are Aura (see rule 303.4), Saga (see rule 714), and Shrine.
        205.3i Lands have their own unique set of subtypes; these subtypes are called land types. The land types are {land_types}. Of that list, the basic land types are Forest, Island, Mountain, Plains, and Swamp.
        205.3k Instants and sorceries share their lists of subtypes; these subtypes are called spell types. The spell types are Adventure (see rule 715), Arcane, and Lesson.
        More text...
    """


class TestFetchAndParseTypes:
    """Tests for fetch_and_parse_types function."""

    @responses.activate
    def test_successful_fetch(self):
        """Test successful fetch and parse of creature and land types."""
        # Mock the initial rules page
        html_content = """
        <html>
            <body>
                <a href="https://media.wizards.com/2023/downloads/MagicCompRules_20231117.txt">
                    Comprehensive Rules
                </a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=html_content,
            status=200,
        )

        # Mock the rules text file
        responses.add(
            responses.GET,
            "https://media.wizards.com/2023/downloads/MagicCompRules_20231117.txt",
            body=make_rules_text(),
            status=200,
        )

        type_lists = rules.fetch_and_parse_types()
        creature_types, land_types = type_lists.creature, type_lists.land

        # Check creature types (Time Lord is always included)
        assert "Time Lord" in creature_types
        assert "Advisor" in creature_types
        assert "Aetherborn" in creature_types
        assert "Ally" in creature_types
        assert "Angel" in creature_types
        assert len(creature_types) >= 50

        # Check land types
        assert "Desert" in land_types
        assert "Forest" in land_types
        assert "Gate" in land_types
        assert "Island" in land_types
        assert "Mountain" in land_types

    @responses.activate
    def test_network_error_on_rules_page(self):
        """Test handling of network error when fetching rules page."""
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=ConnectionError("Network error"),
        )

        with pytest.raises(ValueError, match="Network error while fetching rules page"):
            rules.fetch_and_parse_types()

    @responses.activate
    def test_timeout_on_rules_page(self):
        """Test handling of timeout when fetching rules page."""
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=Timeout("Request timeout"),
        )

        with pytest.raises(ValueError, match="Network error while fetching rules page"):
            rules.fetch_and_parse_types()

    @responses.activate
    def test_http_error_on_rules_page(self):
        """Test handling of HTTP error when fetching rules page."""
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            status=404,
        )

        with pytest.raises(ValueError, match="HTTP error while fetching rules page"):
            rules.fetch_and_parse_types()

    @responses.activate
    def test_no_txt_links_found(self):
        """Test error when no TXT links are found on rules page."""
        html_content = """
        <html>
            <body>
                <p>No links here</p>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=html_content,
            status=200,
        )

        with pytest.raises(
            ValueError, match="Couldn't find the link to the comprehensive rules text file"
        ):
            rules.fetch_and_parse_types()

    @responses.activate
    def test_retry_with_multiple_txt_links(self):
        """Test that function tries multiple TXT links if first fails."""
        html_content = """
        <html>
            <body>
                <a href="https://media.wizards.com/CompRules_broken.txt">Broken</a>
                <a href="https://media.wizards.com/CompRules_working.txt">Working</a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=html_content,
            status=200,
        )

        # First TXT link fails
        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules_broken.txt",
            status=404,
        )

        # Second TXT link succeeds
        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules_working.txt",
            body=make_rules_text(),
            status=200,
        )

        type_lists = rules.fetch_and_parse_types()
        creature_types, land_types = type_lists.creature, type_lists.land

        assert "Advisor" in creature_types
        assert "Desert" in land_types

    @responses.activate
    def test_all_txt_links_fail(self):
        """Test error when all TXT links fail."""
        html_content = """
        <html>
            <body>
                <a href="https://media.wizards.com/CompRules1.txt">Link 1</a>
                <a href="https://media.wizards.com/CompRules2.txt">Link 2</a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=html_content,
            status=200,
        )

        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules1.txt",
            status=404,
        )

        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules2.txt",
            status=500,
        )

        with pytest.raises(ValueError, match="Failed to download comprehensive rules"):
            rules.fetch_and_parse_types()

    @responses.activate
    def test_creature_types_not_found(self):
        """Test error when creature types pattern not found in rules."""
        html_content = """
        <html>
            <body>
                <a href="https://media.wizards.com/CompRules.txt">Rules</a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=html_content,
            status=200,
        )

        # Rules text missing creature types section
        rules_text = """
        Some text but no creature types section.
        205.3i Lands have their own unique set of subtypes; these subtypes are called land types. The land types are Desert. Of that list
        """
        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules.txt",
            body=rules_text,
            status=200,
        )

        with pytest.raises(ValueError, match="Couldn't find creature types in the rules"):
            rules.fetch_and_parse_types()

    @responses.activate
    def test_land_types_not_found(self):
        """Test error when land types pattern not found in rules."""
        html_content = """
        <html>
            <body>
                <a href="https://media.wizards.com/CompRules.txt">Rules</a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=html_content,
            status=200,
        )

        # Rules text with creature types but missing land types section
        rules_text = f"""
        All other creature types are one word long: {SAMPLE_CREATURE_TYPES}.
        Some text but no land types section.
        """
        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules.txt",
            body=rules_text,
            status=200,
        )

        with pytest.raises(ValueError, match="Couldn't find land types in the rules"):
            rules.fetch_and_parse_types()

    @responses.activate
    def test_relative_url_handling(self):
        """Test that relative URLs are properly resolved."""
        html_content = """
        <html>
            <body>
                <a href="/downloads/CompRules.txt">Rules</a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=html_content,
            status=200,
        )

        responses.add(
            responses.GET,
            "https://magic.wizards.com/downloads/CompRules.txt",
            body=make_rules_text(),
            status=200,
        )

        type_lists = rules.fetch_and_parse_types()
        creature_types, land_types = type_lists.creature, type_lists.land

        assert "Advisor" in creature_types
        assert "Desert" in land_types

    @responses.activate
    def test_curly_quote_replacement(self):
        """Test that curly quotes are replaced with straight quotes."""
        html_content = """
        <html>
            <body>
                <a href="https://media.wizards.com/CompRules.txt">Rules</a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=html_content,
            status=200,
        )

        # Use curly quote in rules text (as in actual MTG comprehensive rules)
        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules.txt",
            body=make_rules_text(
                creature_types=SAMPLE_CREATURE_TYPES + ", Urza\u2019s",
                land_types=SAMPLE_LAND_TYPES + ", Urza\u2019s",
            ),
            status=200,
        )

        type_lists = rules.fetch_and_parse_types()
        creature_types, land_types = type_lists.creature, type_lists.land

        # Check that curly quotes were normalized to straight quotes
        assert "Urza's" in creature_types
        assert "Urza's" in land_types

    @responses.activate
    def test_request_exception_on_rules_page(self):
        """Test handling of general request exception when fetching rules page."""
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=RequestException("Some other error"),
        )

        with pytest.raises(ValueError, match="Request error while fetching rules page"):
            rules.fetch_and_parse_types()

    @responses.activate
    def test_parsing_error_on_rules_page(self):
        """Test handling of HTML parsing error."""
        # Return invalid HTML that will cause parsing issues
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body="<html><invalid>",
            status=200,
        )

        # BeautifulSoup is very forgiving, so this won't actually raise an error
        # But we can still test the no-links-found path
        with pytest.raises(
            ValueError, match="Couldn't find the link to the comprehensive rules text file"
        ):
            rules.fetch_and_parse_types()

    @responses.activate
    def test_network_error_on_txt_download(self):
        """Test handling of network error when downloading TXT file."""
        html_content = """
        <html>
            <body>
                <a href="https://media.wizards.com/CompRules.txt">Rules</a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=html_content,
            status=200,
        )

        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules.txt",
            body=ConnectionError("Network error"),
        )

        with pytest.raises(ValueError, match="Failed to download comprehensive rules"):
            rules.fetch_and_parse_types()

    @responses.activate
    def test_timeout_on_txt_download(self):
        """Test handling of timeout when downloading TXT file."""
        html_content = """
        <html>
            <body>
                <a href="https://media.wizards.com/CompRules.txt">Rules</a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=html_content,
            status=200,
        )

        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules.txt",
            body=Timeout("Timeout"),
        )

        with pytest.raises(ValueError, match="Failed to download comprehensive rules"):
            rules.fetch_and_parse_types()

    @responses.activate
    def test_request_exception_on_txt_download(self):
        """Test handling of request exception when downloading TXT file."""
        html_content = """
        <html>
            <body>
                <a href="https://media.wizards.com/CompRules.txt">Rules</a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=html_content,
            status=200,
        )

        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules.txt",
            body=RequestException("Some error"),
        )

        with pytest.raises(ValueError, match="Failed to download comprehensive rules"):
            rules.fetch_and_parse_types()


class TestParseTypes:
    def test_extracts_all_subtype_lists(self):
        type_lists = rules.parse_types(make_rules_text())

        assert "Time Lord" in type_lists.creature
        assert "Urza's" in type_lists.land
        assert "Power-Plant" in type_lists.land
        # Cross-references such as "(see rule 301.5)" contain periods; they must not
        # end the list early or end up in type names.
        assert {"Clue", "Equipment", "Food", "Fortification", "Vehicle"} <= type_lists.artifact
        assert {"Aura", "Saga", "Shrine"} <= type_lists.enchantment
        assert {"Adventure", "Arcane", "Lesson"} <= type_lists.spell
        for types in (type_lists.artifact, type_lists.enchantment, type_lists.spell):
            assert not any("(" in t or "see rule" in t for t in types)

    def test_missing_optional_lists_fall_back_to_defaults(self):
        text = "\n".join(line for line in make_rules_text().splitlines() if "205.3g" not in line)

        type_lists = rules.parse_types(text)

        assert type_lists.artifact == rules.ARTIFACT_TYPES
        assert {"Aura", "Saga", "Shrine"} <= type_lists.enchantment

    def test_built_in_types_are_kept_alongside_new_ones(self):
        text = make_rules_text().replace("Aura (see rule 303.4)", "Aura, Plot")

        type_lists = rules.parse_types(text)

        assert "Plot" in type_lists.enchantment
        assert type_lists.enchantment >= rules.ENCHANTMENT_TYPES


class TestTypeListsStorage:
    def test_round_trip(self, tmp_path):
        original = rules.parse_types(make_rules_text())
        path = tmp_path / "rules" / "types.json"

        original.save(path)

        assert rules.TypeLists.load(path) == original

    def test_empty_lists_are_not_loaded(self):
        assert not rules.TypeLists().loaded
