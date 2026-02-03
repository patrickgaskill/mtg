"""Shared pytest fixtures for all tests."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture
def sample_card():
    """A basic sample card with common fields."""
    return {
        "name": "Lightning Bolt",
        "mana_cost": "{R}",
        "cmc": 1.0,
        "type_line": "Instant",
        "oracle_text": "Lightning Bolt deals 3 damage to any target.",
        "colors": ["R"],
        "set": "lea",
        "set_name": "Limited Edition Alpha",
        "collector_number": "161",
        "released_at": "1993-08-05",
        "rarity": "common",
        "border_color": "black",
        "layout": "normal",
        "finishes": ["nonfoil"],
        "promo": False,
        "image_uris": {
            "small": "https://example.com/small.jpg",
            "normal": "https://example.com/normal.jpg",
            "large": "https://example.com/large.jpg",
        },
    }


@pytest.fixture
def sample_creature():
    """A sample creature card with power and toughness."""
    return {
        "name": "Grizzly Bears",
        "mana_cost": "{1}{G}",
        "cmc": 2.0,
        "type_line": "Creature — Bear",
        "oracle_text": "",
        "power": "2",
        "toughness": "2",
        "colors": ["G"],
        "set": "lea",
        "set_name": "Limited Edition Alpha",
        "collector_number": "201",
        "released_at": "1993-08-05",
        "rarity": "common",
        "border_color": "black",
        "layout": "normal",
        "finishes": ["nonfoil"],
        "promo": False,
    }


@pytest.fixture
def sample_dfc_card():
    """A sample double-faced card."""
    return {
        "name": "Delver of Secrets // Insectile Aberration",
        "type_line": "Creature — Human Wizard // Creature — Human Insect",
        "layout": "transform",
        "set": "isd",
        "set_name": "Innistrad",
        "collector_number": "51",
        "released_at": "2011-09-30",
        "card_faces": [
            {
                "name": "Delver of Secrets",
                "mana_cost": "{U}",
                "type_line": "Creature — Human Wizard",
                "oracle_text": "At the beginning of your upkeep, look at the top card.",
                "power": "1",
                "toughness": "1",
            },
            {
                "name": "Insectile Aberration",
                "mana_cost": "",
                "type_line": "Creature — Human Insect",
                "oracle_text": "Flying",
                "power": "3",
                "toughness": "2",
            },
        ],
    }


@pytest.fixture
def sample_changeling():
    """A sample card with changeling (all creature types)."""
    return {
        "name": "Mistform Ultimus",
        "mana_cost": "{3}{U}",
        "cmc": 4.0,
        "type_line": "Legendary Creature — Illusion",
        "oracle_text": "Mistform Ultimus is every creature type.",
        "power": "3",
        "toughness": "3",
        "colors": ["U"],
        "set": "lgn",
        "set_name": "Legions",
        "collector_number": "45",
        "released_at": "2003-02-03",
    }


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_cards_list(sample_card, sample_creature, sample_dfc_card):
    """A list of sample cards for batch processing tests."""
    return [sample_card, sample_creature, sample_dfc_card]


@pytest.fixture
def mock_scryfall_response():
    """Mock response from Scryfall bulk data API."""
    return {
        "object": "list",
        "data": [
            {
                "object": "bulk_data",
                "id": "test-id",
                "type": "default_cards",
                "updated_at": datetime.now().isoformat(),
                "name": "Default Cards",
                "description": "All cards in the default format",
                "download_uri": "https://example.com/cards.json",
                "size": 100000000,
            }
        ],
    }
