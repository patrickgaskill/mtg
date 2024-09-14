import re
from datetime import date, datetime
from typing import Any, Dict, Set, Tuple

# Constants
BASIC_LAND_TYPES = {"Forest", "Island", "Mountain", "Plains", "Swamp"}
NON_TRADITIONAL_SET_TYPES = {"memorabilia", "funny"}
NON_TRADITIONAL_LAYOUTS = {"emblem", "token"}
NON_TRADITIONAL_BORDERS = {"silver", "gold"}


def extract_types(card: Dict[str, Any]) -> Set[str]:
    text = card.get("type_line", "").replace("Time Lord", "Time-Lord")
    words = re.findall(r"\b[\w\-']+\b", text)
    return set(word.replace("Time-Lord", "Time Lord") for word in words)


def get_sort_key(card: Dict[str, Any]) -> Tuple[date, str, int, str]:
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
    return card.get("name") == "Mistform Ultimus" or "Changeling" in card.get(
        "keywords", []
    )


def is_traditional_card(
    card: Dict[str, Any],
    non_traditional_set_types: Set[str] = NON_TRADITIONAL_SET_TYPES,
    non_traditional_layouts: Set[str] = NON_TRADITIONAL_LAYOUTS,
    non_traditional_borders: Set[str] = NON_TRADITIONAL_BORDERS,
) -> bool:
    if card.get("set_type") in non_traditional_set_types:
        return False
    if card.get("layout") in non_traditional_layouts:
        return False
    if card.get("set") == "past":
        return False
    if card.get("border_color") in non_traditional_borders:
        return False
    return True


def generalize_mana_cost(mana_cost):
    """
    Generalizes a mana cost string by replacing color symbols with generic symbols.

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
