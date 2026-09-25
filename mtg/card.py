"""A normalized view of a Scryfall card, built once per card before aggregation.

Scryfall stores some fields on the card and others on its faces, depending on the
layout: transform and modal double-faced cards keep illustrations, images, and
power/toughness on `card_faces`, while split and adventure cards share one image.
`Card.from_scryfall` resolves those differences once, so aggregators never touch the
raw JSON. It also keeps only the fields reports use, which keeps memory low when
aggregators hold on to thousands of cards.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from mtg.card_utils import (
    extract_creature_subtypes,
    extract_types,
    get_card_image_uri,
    get_illustration_key,
    get_sort_key,
    is_traditional_card,
)
from mtg.constants import LAND_TYPES, NON_CREATURE_LAND_SUBTYPES

MISTFORM_ULTIMUS = "Mistform Ultimus"


@dataclass(frozen=True, slots=True, eq=False)
class Face:
    """One face of a card. Single-faced cards have one face mirroring the card."""

    name: str
    type_line: str
    mana_cost: str
    oracle_text: str
    power: str
    toughness: str
    loyalty: str
    defense: str
    colors: tuple[str, ...]
    keywords: tuple[str, ...]
    # This face's own image, or "" when the card shares one image across faces.
    image_uri: str
    types: frozenset[str]

    @property
    def is_all_creature_types(self) -> bool:
        """Changelings and Mistform Ultimus have every creature type."""
        return self.name == MISTFORM_ULTIMUS or "Changeling" in self.keywords

    @classmethod
    def from_scryfall(cls, data: dict[str, Any], keywords: tuple[str, ...]) -> "Face":
        return cls(
            name=data.get("name") or "",
            type_line=data.get("type_line") or "",
            mana_cost=data.get("mana_cost") or "",
            oracle_text=data.get("oracle_text") or "",
            power=data.get("power") or "",
            toughness=data.get("toughness") or "",
            loyalty=data.get("loyalty") or "",
            defense=data.get("defense") or "",
            colors=tuple(data.get("colors") or ()),
            keywords=keywords,
            image_uri=(data.get("image_uris") or {}).get("normal", ""),
            types=frozenset(extract_types(data)),
        )


@dataclass(frozen=True, slots=True, eq=False)
class Card:
    """A single printing of a card."""

    name: str
    set: str
    set_type: str
    layout: str
    border_color: str
    collector_number: str
    released_at: str
    released_date: date | None
    type_line: str
    mana_cost: str
    # Rules text of every face, joined with spaces.
    oracle_text: str
    power: str
    toughness: str
    colors: tuple[str, ...]
    keywords: tuple[str, ...]
    finishes: tuple[str, ...]
    promo_types: tuple[str, ...]
    scryfall_uri: str
    image_uri: str
    illustration_key: str | None
    faces: tuple[Face, ...]
    is_multiface: bool
    sort_key: tuple[date, str, int, str]
    is_traditional: bool
    types: frozenset[str]
    # Sorted, so rows derived from one card come out in a stable order.
    creature_subtypes: tuple[str, ...]
    is_all_creature_types: bool

    @property
    def is_token(self) -> bool:
        return self.layout == "token"

    def link(self, face: Face | None = None) -> dict[str, str]:
        """Scryfall link and image for report rows, preferring the face's own image."""
        return {
            "scryfall_uri": self.scryfall_uri,
            "image_uri": (face.image_uri if face else "") or self.image_uri,
        }

    @classmethod
    def from_scryfall(
        cls,
        data: dict[str, Any],
        non_creature_subtypes: frozenset[str] = NON_CREATURE_LAND_SUBTYPES,
        land_types: frozenset[str] = LAND_TYPES,
    ) -> "Card":
        """Build a Card from a Scryfall card object.

        `non_creature_subtypes` and `land_types` tell creature subtypes apart from
        other subtypes on the same type line; pass the rules type lists when loaded.
        """
        keywords = tuple(data.get("keywords") or ())
        raw_faces = [f for f in data.get("card_faces") or () if isinstance(f, dict)]
        is_multiface = bool(raw_faces)
        if is_multiface:
            # Scryfall doesn't list keywords per face.
            faces = tuple(Face.from_scryfall(f, ()) for f in raw_faces)
            oracle_text = " ".join(face.oracle_text for face in faces)
        else:
            faces = (Face.from_scryfall(data, keywords),)
            oracle_text = data.get("oracle_text") or ""

        released_at = data.get("released_at") or ""
        type_line = data.get("type_line") or ""
        name = data.get("name") or ""
        return cls(
            name=name,
            set=data.get("set") or "",
            set_type=data.get("set_type") or "",
            layout=data.get("layout") or "",
            border_color=data.get("border_color") or "",
            collector_number=data.get("collector_number") or "",
            released_at=released_at,
            released_date=date.fromisoformat(released_at) if released_at else None,
            type_line=type_line,
            mana_cost=data.get("mana_cost") or "",
            oracle_text=oracle_text,
            power=data.get("power") or "",
            toughness=data.get("toughness") or "",
            colors=tuple(data.get("colors") or ()),
            keywords=keywords,
            finishes=tuple(data.get("finishes") or ()),
            promo_types=tuple(data.get("promo_types") or ()),
            scryfall_uri=data.get("scryfall_uri") or "",
            image_uri=get_card_image_uri(data),
            illustration_key=get_illustration_key(data),
            faces=faces,
            is_multiface=is_multiface,
            sort_key=get_sort_key(data),
            is_traditional=is_traditional_card(data),
            types=frozenset(extract_types(data)),
            creature_subtypes=tuple(
                sorted(extract_creature_subtypes(type_line, non_creature_subtypes, land_types))
            ),
            is_all_creature_types=name == MISTFORM_ULTIMUS or "Changeling" in keywords,
        )
