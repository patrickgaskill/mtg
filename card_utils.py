import re
from datetime import date, datetime
from typing import Any, Dict, Set, Tuple

from aggregators.constants import (
    NON_TRADITIONAL_BORDERS,
    NON_TRADITIONAL_LAYOUTS,
    NON_TRADITIONAL_SET_TYPES,
)

# Constants
BASIC_LAND_TYPES = {"Forest", "Island", "Mountain", "Plains", "Swamp"}


def extract_types(card: Dict[str, Any]) -> Set[str]:
    """
    Extract the types from a card's type line.

    Args:
        card (Dict[str, Any]): A dictionary representing a card.

    Returns:
        Set[str]: A set of types extracted from the card's type line.
    """
    text = card.get("type_line", "").replace("Time Lord", "Time-Lord")
    words = re.findall(r"\b[\w\-']+\b", text)
    return set(word.replace("Time-Lord", "Time Lord") for word in words)


def get_sort_key(card: Dict[str, Any]) -> Tuple[date, str, int, str]:
    """
    Generate a sort key for a card.

    Args:
        card (Dict[str, Any]): A dictionary representing a card.

    Returns:
        Tuple[date, str, int, str]: A tuple containing the release date, set name,
        parsed collector number, and original collector number string.
    """
    released_at = card.get("released_at")
    release_date = (
        date.fromisoformat(released_at) if released_at else datetime.max.date()
    )

    collector_number = card.get("collector_number", "")
    try:
        parsed_number = int(re.sub(r"[^\d]+", "", collector_number))
    except ValueError:
        parsed_number = 0

    return release_date, card.get("set", ""), parsed_number, collector_number


def is_all_creature_types(card: Dict[str, Any]) -> bool:
    """
    Check if a card has all creature types.

    Args:
        card (Dict[str, Any]): A dictionary representing a card.

    Returns:
        bool: True if the card has all creature types, False otherwise.
    """
    return card.get("name") == "Mistform Ultimus" or "Changeling" in card.get(
        "keywords", []
    )


def is_permanent(card: Dict[str, Any]) -> bool:
    """
    Determine if a card is a permanent.

    Args:
        card (Dict[str, Any]): A dictionary representing a card.

    Returns:
        bool: True if the card is a permanent, False otherwise.
    """
    permanent_types = {
        "Artifact",
        "Battle",
        "Creature",
        "Enchantment",
        "Land",
        "Planeswalker",
    }
    card_types = extract_types(card)
    return any(ptype in card_types for ptype in permanent_types)


def is_traditional_card(
    card: Dict[str, Any],
    non_traditional_set_types: Set[str] = NON_TRADITIONAL_SET_TYPES,
    non_traditional_layouts: Set[str] = NON_TRADITIONAL_LAYOUTS,
    non_traditional_borders: Set[str] = NON_TRADITIONAL_BORDERS,
) -> bool:
    """
    Determine if a card is considered traditional.

    Args:
        card (Dict[str, Any]): A dictionary representing a card.
        non_traditional_set_types (Set[str], optional): Set of non-traditional set types.
        non_traditional_layouts (Set[str], optional): Set of non-traditional layouts.
        non_traditional_borders (Set[str], optional): Set of non-traditional border colors.

    Returns:
        bool: True if the card is traditional, False otherwise.
    """
    if card.get("set_type") in non_traditional_set_types:
        return False
    if card.get("layout") in non_traditional_layouts:
        return False
    if card.get("set") == "past":
        return False
    if card.get("border_color") in non_traditional_borders:
        return False
    return True


def generalize_mana_cost(mana_cost: str) -> str:
    """
    Generalizes a mana cost string by replacing color symbols with generic symbols.

    Args:
        mana_cost (str): A string representing a mana cost.

    Returns:
        str: A generalized mana cost string.

    Examples:
        >>> generalize_mana_cost("{2}")
        '{2}'
        >>> generalize_mana_cost("{W}{W}")
        '{M}{M}'
        >>> generalize_mana_cost("{W}{U}{R}")
        '{M}{N}{O}'
        >>> generalize_mana_cost("{W}{U}{B}{R}{G}")
        '{W}{U}{B}{R}{G}'
        >>> generalize_mana_cost("{2/W}{2/U}")
        '{2/M}{2/N}'
        >>> generalize_mana_cost("{W/P}{W/U}{2/W}")
        '{M/P}{M/N}{2/M}'
    """
    colors = "WUBRG"
    generics = "MNOP"
    color_map = {}

    for c in mana_cost:
        if c in colors and c not in color_map:
            if len(color_map) < len(generics):
                color_map[c] = generics[len(color_map)]
            else:
                return mana_cost

    return "".join(color_map.get(c, c) for c in mana_cost)


def get_card_image_uri(card: Dict[str, Any], size: str = "normal") -> str:
    """
    Extract the image URI for a card.

    Args:
        card (Dict[str, Any]): A dictionary representing a card.
        size (str, optional): The image size to retrieve. Defaults to "normal".

    Returns:
        str: The image URI, or empty string if not available.
    """
    # For double-faced or multi-faced cards, Scryfall stores image URIs on the faces.
    card_faces = card.get("card_faces")
    if card_faces:
        # Use the first valid face dict; explicitly handle unlikely None or non-dict entries.
        first_face = None
        for face in card_faces:
            if isinstance(face, dict):
                first_face = face
                break
        if first_face is not None:
            face_image_uris = first_face.get("image_uris")
            if face_image_uris:
                return face_image_uris.get(size, "")

    # Fallback for single-faced cards or when face image URIs are unavailable.
    image_uris = card.get("image_uris")
    if image_uris:
        return image_uris.get(size, "")

    return ""
