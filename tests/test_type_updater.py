"""Tests for type_updater.py functions."""

import pytest
import responses
from requests.exceptions import ConnectionError, RequestException, Timeout

import type_updater


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
        rules_text = """
        Some text before...
        All other creature types are one word long: Advisor, Aetherborn, Ally, Angel.
        More text...
        205.3i Lands have their own unique set of subtypes; these subtypes are called land types. The land types are Desert, Forest, Gate, Island, and Mountain. Of that list, the basic land types are Forest, Island, Mountain, Plains, and Swamp.
        More text...
        """
        responses.add(
            responses.GET,
            "https://media.wizards.com/2023/downloads/MagicCompRules_20231117.txt",
            body=rules_text,
            status=200,
        )

        creature_types, land_types = type_updater.fetch_and_parse_types()

        # Check creature types (Time Lord is always included)
        assert "Time Lord" in creature_types
        assert "Advisor" in creature_types
        assert "Aetherborn" in creature_types
        assert "Ally" in creature_types
        assert "Angel" in creature_types

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
            type_updater.fetch_and_parse_types()

    @responses.activate
    def test_timeout_on_rules_page(self):
        """Test handling of timeout when fetching rules page."""
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=Timeout("Request timeout"),
        )

        with pytest.raises(ValueError, match="Network error while fetching rules page"):
            type_updater.fetch_and_parse_types()

    @responses.activate
    def test_http_error_on_rules_page(self):
        """Test handling of HTTP error when fetching rules page."""
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            status=404,
        )

        with pytest.raises(ValueError, match="HTTP error while fetching rules page"):
            type_updater.fetch_and_parse_types()

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
            type_updater.fetch_and_parse_types()

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
        rules_text = """
        All other creature types are one word long: Advisor.
        205.3i Lands have their own unique set of subtypes; these subtypes are called land types. The land types are Desert. Of that list
        """
        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules_working.txt",
            body=rules_text,
            status=200,
        )

        creature_types, land_types = type_updater.fetch_and_parse_types()

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
            type_updater.fetch_and_parse_types()

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
            type_updater.fetch_and_parse_types()

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

        # Rules text missing land types section
        rules_text = """
        All other creature types are one word long: Advisor.
        Some text but no land types section.
        """
        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules.txt",
            body=rules_text,
            status=200,
        )

        with pytest.raises(ValueError, match="Couldn't find land types in the rules"):
            type_updater.fetch_and_parse_types()

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

        rules_text = """
        All other creature types are one word long: Advisor.
        205.3i Lands have their own unique set of subtypes; these subtypes are called land types. The land types are Desert. Of that list
        """
        responses.add(
            responses.GET,
            "https://magic.wizards.com/downloads/CompRules.txt",
            body=rules_text,
            status=200,
        )

        creature_types, land_types = type_updater.fetch_and_parse_types()

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

        # Use curly quote in rules text
        rules_text = """
        All other creature types are one word long: Advisor, Urza's.
        205.3i Lands have their own unique set of subtypes; these subtypes are called land types. The land types are Desert, Urza's. Of that list
        """
        responses.add(
            responses.GET,
            "https://media.wizards.com/CompRules.txt",
            body=rules_text,
            status=200,
        )

        creature_types, land_types = type_updater.fetch_and_parse_types()

        # Check that types with apostrophes are parsed correctly
        assert any("Urza's" in t or "Urza" in t for t in creature_types)
        assert any("Urza's" in t or "Urza" in t for t in land_types)

    @responses.activate
    def test_request_exception_on_rules_page(self):
        """Test handling of general request exception when fetching rules page."""
        responses.add(
            responses.GET,
            "https://magic.wizards.com/en/rules",
            body=RequestException("Some other error"),
        )

        with pytest.raises(ValueError, match="Request error while fetching rules page"):
            type_updater.fetch_and_parse_types()

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
            type_updater.fetch_and_parse_types()

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
            type_updater.fetch_and_parse_types()

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
            type_updater.fetch_and_parse_types()

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
            type_updater.fetch_and_parse_types()
