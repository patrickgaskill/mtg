"""Aggregators for counting card appearances by character."""

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from card_utils import get_card_link_data, get_sort_key, is_traditional_card

from .base import Aggregator

# Scryfall type lines separate types from subtypes with an em dash.
TYPE_LINE_SEPARATOR = "—"

# Older card names put the character first and a title after ("Kaervek the
# Merciless", "Jhoira of the Ghitu"), so the name before one of these
# separators is the character.
NAME_SEPARATORS = (" the ", " of ")

# Single words that look like a name before a separator but are really titles,
# so "Lord of Tresserhorn" isn't filed under a character named "Lord".
TITLE_WORDS = {
    "Avatar",
    "Baron",
    "Baroness",
    "Captain",
    "Champion",
    "General",
    "Guardian",
    "Herald",
    "Keeper",
    "King",
    "Lady",
    "Lord",
    "Master",
    "Mistress",
    "Prince",
    "Princess",
    "Queen",
    "Voice",
    "Warlord",
}


def split_type_line(type_line: str) -> tuple[str, str]:
    """Split a single face's type line into its types and subtypes."""
    if TYPE_LINE_SEPARATOR not in type_line:
        return type_line.strip(), ""
    types, subtypes = type_line.split(TYPE_LINE_SEPARATOR, 1)
    return types.strip(), subtypes.strip()


def iter_faces(card: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (name, type line) for each face of a card."""
    faces = card.get("card_faces")
    if faces:
        return [
            (face.get("name", ""), face.get("type_line", ""))
            for face in faces
            if isinstance(face, dict)
        ]
    return [(card.get("name", ""), card.get("type_line", ""))]


def derive_character_name(card_name: str) -> str:
    """
    Derive the character's name from a card name.

    Cuts the title off the end: "Kaervek, the Spiteful", "Kaervek the Merciless"
    and "Jhoira of the Ghitu" all name the character first.
    """
    root = card_name.split(",", 1)[0].strip()

    # Use whichever separator comes first, so "Jhoira of the Ghitu" cuts at
    # " of " rather than " the ".
    positions = [(root.find(sep), sep) for sep in NAME_SEPARATORS if sep in root]
    if positions:
        index, separator = min(positions)
        prefix = root[:index].strip()
        if prefix and prefix not in TITLE_WORDS:
            root = prefix

    return root


def is_planeswalker_face(type_line: str) -> bool:
    """Check whether a face is a planeswalker."""
    types, _ = split_type_line(type_line)
    return "Planeswalker" in types.split()


def is_legendary_creature_face(type_line: str) -> bool:
    """Check whether a face is a legendary creature."""
    types = split_type_line(type_line)[0].split()
    return "Legendary" in types and "Creature" in types


def is_rebalanced_card(card: dict[str, Any]) -> bool:
    """Check whether a card is an Alchemy rebalance ("A-") of another card."""
    return bool(card.get("digital")) and card.get("name", "").startswith("A-")


class CharacterAppearanceAggregator(Aggregator):
    """Count how many distinct cards represent each character."""

    def __init__(
        self,
        characters_file: Path,
        planeswalkers_only: bool = False,
        description: str = "",
    ):
        if planeswalkers_only:
            name = "planeswalker_card_appearances"
            display_name = "Most Card Appearances by Planeswalker"
            subject = "planeswalker"
        else:
            name = "character_card_appearances"
            display_name = "Most Card Appearances by Character"
            subject = "character"

        super().__init__(
            name,
            display_name,
            description,
            explanation=(
                f"How many distinct cards represent each {subject}. A card counts only when it"
                " <em>is</em> that character, not when it merely depicts them or names a spell"
                " they cast, so <em>Urza's Rage</em> is not an Urza card but <em>Blind Seer</em>"
                " (Urza in disguise) is. Reprints of the same card count once, and the dates are"
                " each card's first printing.\n\n"
                "Cards are matched two ways: a planeswalker card represents the character named by"
                " its planeswalker subtype (<em>Legendary Planeswalker — Jace</em>), and a"
                " legendary creature card represents the character its name starts with"
                " (<em>Kaervek, the Spiteful</em> and <em>Kaervek the Merciless</em> are both"
                " Kaervek). Exceptions, aliases and cards that represent two characters are"
                " curated by hand in <code>data/manual/characters.yaml</code>. Cards from funny"
                " sets, memorabilia, Vanguard and Alchemy rebalances are excluded."
            ),
        )
        self.planeswalkers_only = planeswalkers_only
        self.card_characters: dict[str, list[str]] = {}
        self.character_names: dict[str, str] = {}
        self.non_character_cards: set[str] = set()
        self.planeswalker_characters: set[str] = set()
        self.load_character_data(characters_file)

        # character -> card name -> minimal card data for display
        self.cards: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self.seen_card_characters: set[str] = set()
        self.seen_non_character_cards: set[str] = set()
        self.used_character_names: set[str] = set()
        self.warned = False

        card_column = {
            "width": 220,
            "cellRenderer": "cardLinkRenderer",
            "cardLinkData": "cardObjects",
        }
        self.column_defs = [
            {
                "field": "character",
                "headerName": "Planeswalker" if planeswalkers_only else "Character",
                "width": 180,
            },
            {
                "field": "count",
                "headerName": "Cards",
                "width": 100,
                "type": "numericColumn",
                "sort": "desc",
            },
            {"field": "firstCard", "headerName": "First Card", **card_column},
            {"field": "firstReleaseDate", "headerName": "First Printed", "width": 120},
            {"field": "latestCard", "headerName": "Latest Card", **card_column},
            {"field": "latestReleaseDate", "headerName": "Latest Printed", "width": 120},
            {
                "field": "cards",
                "headerName": "All Cards",
                "width": 320,
                "wrapText": True,
                "autoHeight": True,
                "suppressAutoSize": True,
                "cellClass": "compact-cell",
                "cellRenderer": "cardLinkRenderer",
                "cardLinkData": "cardObjects",
            },
        ]

    def load_character_data(self, file_path: Path) -> None:
        """Load curated character data from a YAML file."""
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except OSError as e:
            self.warnings.append(f"Error: Failed to load character data from {file_path}: {e}")
            return
        except yaml.YAMLError as e:
            self.warnings.append(f"Error: Failed to parse character data file {file_path}: {e}")
            return

        for card_name, curated in (data.get("card_characters") or {}).items():
            characters = [curated] if isinstance(curated, str) else list(curated)
            self.card_characters[card_name] = characters

        self.character_names = dict(data.get("character_names") or {})
        self.non_character_cards = set(data.get("non_character_cards") or [])
        self.planeswalker_characters = set(data.get("planeswalker_characters") or [])

    def canonical_name(self, character: str) -> str:
        """Map a derived character name onto its canonical name."""
        canonical = self.character_names.get(character)
        if canonical is None:
            return character
        self.used_character_names.add(character)
        return canonical

    def characters_for_card(self, card: dict[str, Any]) -> tuple[set[str], set[str]]:
        """
        Determine which characters a card represents.

        Returns the card's characters and, of those, the ones named by a
        planeswalker subtype on this card.
        """
        faces = iter_faces(card)

        planeswalker_characters = set()
        for _, type_line in faces:
            if not is_planeswalker_face(type_line):
                continue
            subtypes = split_type_line(type_line)[1]
            if subtypes:
                # Planeswalker subtypes are single words, but the whole subtype
                # string is kept so a multi-word type stays one character.
                planeswalker_characters.add(self.canonical_name(subtypes))

        curated = self.card_characters.get(card.get("name", ""))
        if curated is not None:
            self.seen_card_characters.add(card["name"])
            characters = {self.canonical_name(character) for character in curated}
            return characters, planeswalker_characters & characters

        characters = set(planeswalker_characters)
        for face_name, type_line in faces:
            if is_planeswalker_face(type_line):
                # A planeswalker without a subtype falls back to its name.
                if not split_type_line(type_line)[1] and face_name:
                    characters.add(self.canonical_name(derive_character_name(face_name)))
            elif is_legendary_creature_face(type_line) and face_name:
                characters.add(self.canonical_name(derive_character_name(face_name)))

        return characters, planeswalker_characters

    def process_card(self, card: dict[str, Any]) -> None:
        name = card.get("name")
        if not name or not is_traditional_card(card) or is_rebalanced_card(card):
            return

        if name in self.non_character_cards:
            self.seen_non_character_cards.add(name)
            return

        characters, planeswalker_characters = self.characters_for_card(card)
        if not characters:
            return

        self.planeswalker_characters.update(planeswalker_characters)

        sort_key = get_sort_key(card)
        for character in characters:
            existing = self.cards[character].get(name)
            # Keep the earliest printing so dates reflect a card's debut.
            if existing is None or sort_key < existing["sortKey"]:
                self.cards[character][name] = {
                    "name": name,
                    "sortKey": sort_key,
                    "releasedAt": card.get("released_at", ""),
                    **get_card_link_data(card),
                }

    def check_curated_data(self) -> None:
        """Warn once about curated entries that never matched a card."""
        if self.warned:
            return
        self.warned = True

        for card_name in sorted(set(self.card_characters) - self.seen_card_characters):
            self.warnings.append(
                f"characters.yaml maps card '{card_name}' to a character,"
                " but no such card was found"
            )
        for card_name in sorted(self.non_character_cards - self.seen_non_character_cards):
            self.warnings.append(
                f"characters.yaml excludes card '{card_name}', but no such card was found"
            )
        for character in sorted(set(self.character_names) - self.used_character_names):
            self.warnings.append(
                f"characters.yaml renames character '{character}', but no card produced that name"
            )

    def get_sorted_data(self) -> list[dict[str, Any]]:
        self.check_curated_data()

        result = []
        for character, cards in self.cards.items():
            if self.planeswalkers_only and character not in self.planeswalker_characters:
                continue

            ordered = sorted(cards.values(), key=lambda entry: entry["sortKey"])
            first, latest = ordered[0], ordered[-1]
            result.append(
                {
                    "character": character,
                    "count": len(ordered),
                    "firstCard": first["name"],
                    "firstReleaseDate": first["releasedAt"],
                    "latestCard": latest["name"],
                    "latestReleaseDate": latest["releasedAt"],
                    "cards": ", ".join(entry["name"] for entry in ordered),
                    "cardObjects": [
                        {
                            "name": entry["name"],
                            "scryfall_uri": entry["scryfall_uri"],
                            "image_uri": entry["image_uri"],
                        }
                        for entry in ordered
                    ],
                }
            )

        return sorted(result, key=lambda row: (-row["count"], row["character"]))
