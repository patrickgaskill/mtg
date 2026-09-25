import re
from datetime import date
from typing import Any

from mtg.constants import (
    CREATURE_SUBTYPE_CARD_TYPES,
    LAND_TYPES,
    NON_CREATURE_LAND_SUBTYPES,
    NON_TRADITIONAL_BORDERS,
    NON_TRADITIONAL_LAYOUTS,
    NON_TRADITIONAL_PROMO_TYPES,
    NON_TRADITIONAL_SET_TYPES,
)

# Constants
BASIC_LAND_TYPES = {"Forest", "Island", "Mountain", "Plains", "Swamp"}


def extract_types(card: dict[str, Any]) -> set[str]:
    """
    Extract the types from a card's type line.

    Args:
        card (dict[str, Any]): A dictionary representing a card.

    Returns:
        set[str]: A set of types extracted from the card's type line.
    """
    text = card.get("type_line", "").replace("Time Lord", "Time-Lord")
    words = re.findall(r"\b[\w\-']+\b", text)
    return {word.replace("Time-Lord", "Time Lord") for word in words}


def extract_creature_subtypes(
    type_line: str,
    non_creature_subtypes: frozenset[str] = NON_CREATURE_LAND_SUBTYPES,
    land_types: frozenset[str] = LAND_TYPES,
) -> set[str]:
    """
    Extract creature subtypes from a type line.

    Returns the creature subtypes of Creature and Kindred (Tribal) faces, or an
    empty set if no face has any. Artifact, enchantment, spell, and land
    subtypes sharing the type line (e.g. "Artifact Creature — Equipment Lizard")
    are dropped. Handles "Time Lord" as a single type and multi-faced cards,
    whose type line lists each face separated by " // ".
    """
    subtypes = set()

    for face in type_line.split(" // "):
        if "—" not in face:
            continue

        supertypes_and_types, subtype_str = face.split("—", 1)
        card_types = set(supertypes_and_types.split())

        if not card_types & CREATURE_SUBTYPE_CARD_TYPES:
            continue

        excluded = non_creature_subtypes
        if "Land" in card_types:
            excluded = excluded | land_types

        # Handle "Time Lord" as a single type
        subtype_str = subtype_str.replace("Time Lord", "Time-Lord")
        for part in subtype_str.split():
            subtype = part.replace("Time-Lord", "Time Lord")
            if subtype not in excluded:
                subtypes.add(subtype)

    return subtypes


def get_sort_key(card: dict[str, Any]) -> tuple[date, str, int, str]:
    """
    Generate a sort key for a card.

    Args:
        card (dict[str, Any]): A dictionary representing a card.

    Returns:
        tuple[date, str, int, str]: A tuple containing the release date, set name,
        parsed collector number, and original collector number string.
    """
    released_at = card.get("released_at")
    release_date = date.fromisoformat(released_at) if released_at else date.max

    collector_number = card.get("collector_number", "")
    try:
        parsed_number = int(re.sub(r"[^\d]+", "", collector_number))
    except ValueError:
        parsed_number = 0

    return release_date, card.get("set", ""), parsed_number, collector_number


def is_permanent(card: dict[str, Any]) -> bool:
    """
    Determine if a card is a permanent.

    Args:
        card (dict[str, Any]): A dictionary representing a card.

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
    card: dict[str, Any],
    non_traditional_set_types: set[str] = NON_TRADITIONAL_SET_TYPES,
    non_traditional_layouts: set[str] = NON_TRADITIONAL_LAYOUTS,
    non_traditional_borders: set[str] = NON_TRADITIONAL_BORDERS,
    non_traditional_promo_types: set[str] = NON_TRADITIONAL_PROMO_TYPES,
) -> bool:
    """
    Determine if a card is considered traditional.

    Args:
        card (dict[str, Any]): A dictionary representing a card.
        non_traditional_set_types (set[str], optional): Set of non-traditional set types.
        non_traditional_layouts (set[str], optional): Set of non-traditional layouts.
        non_traditional_borders (set[str], optional): Set of non-traditional border colors.
        non_traditional_promo_types (set[str], optional): Set of non-traditional promo types.

    Returns:
        bool: True if the card is traditional, False otherwise.
    """
    if card.get("set_type") in non_traditional_set_types:
        return False
    if card.get("layout") in non_traditional_layouts:
        return False
    if card.get("set") == "past":
        return False
    if non_traditional_promo_types.intersection(card.get("promo_types", [])):
        return False
    return card.get("border_color") not in non_traditional_borders


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


def get_illustration_key(card: dict[str, Any]) -> str | None:
    """
    Identify the artwork of a printing.

    Single-image cards carry a top-level illustration_id. Double-faced cards
    (transform, modal DFC, etc.) carry one per face instead, so their face IDs
    are joined into a single key identifying the printing's full set of art.

    Returns:
        str | None: The illustration key, or None if the card has no art IDs.
    """
    illustration_id = card.get("illustration_id")
    if illustration_id:
        return illustration_id
    face_ids = [
        face["illustration_id"]
        for face in card.get("card_faces") or []
        if isinstance(face, dict) and face.get("illustration_id")
    ]
    return "/".join(face_ids) if face_ids else None


def get_card_image_uri(card: dict[str, Any], size: str = "normal") -> str:
    """
    Extract the image URI for a card.

    Args:
        card (dict[str, Any]): A dictionary representing a card.
        size (str, optional): The image size to retrieve. Defaults to "normal".

    Returns:
        str: The image URI, or empty string if not available.
    """
    # For double-faced or multi-faced cards, Scryfall stores image URIs on the faces.
    card_faces = card.get("card_faces")
    if card_faces:
        # Use the first valid face dict from the array.
        for face in card_faces:
            if isinstance(face, dict):
                face_image_uris = face.get("image_uris")
                if face_image_uris:
                    return face_image_uris.get(size, "")
                # Stop after checking first valid dict face, even if it lacks images
                break

    # Fallback for single-faced cards or when face image URIs are unavailable.
    image_uris = card.get("image_uris")
    if image_uris:
        return image_uris.get(size, "")

    return ""
