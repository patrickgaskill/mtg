"""Aggregators for analyzing card types."""

from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from card_utils import (
    BASIC_LAND_TYPES,
    extract_types,
    get_sort_key,
    is_all_creature_types,
    is_permanent,
    is_traditional_card,
)

from .base import Aggregator, logger


class MaximalPrintedTypesAggregator(Aggregator):
    """Find cards with maximal printed type combinations."""

    def __init__(
        self,
        all_creature_types_file: Path,
        all_land_types_file: Path,
        description: str = "",
    ):
        super().__init__(
            "maximal_printed_types",
            "Maximal Printed Types",
            description,
            explanation="""
## What are Maximal Printed Types?

This report shows cards that have the maximum number of types **as printed on the card**,
without considering any external effects or abilities.

A card is considered to have "maximal types" if there's no other card whose printed types
are a strict superset of this card's types. In other words, you can't add more types to
this card without removing at least one existing type.

**Special handling:**
- Cards with **Changeling** (like Mistform Ultimus) count as having all creature types
- **Planar Nexus** counts as having all nonbasic land types
- Only traditional Magic cards are included (no silver-bordered, tokens, etc.)

**Important notes:**
- This differs from "Maximal Types with Global Effects" which considers what types cards could have when affected by other cards in play
- **Type lag:** There may be a delay between when new creature or land types appear on cards and when they're officially added to the comprehensive rules.
  During this time, cards with Changeling or similar effects may not show the new types in this report.
  Types are updated via the `update-types` command.
            """,
        )
        self.maximal_types: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        self.column_defs = [
            {"field": "types", "headerName": "Types", "width": 240},
            {
                "field": "name",
                "headerName": "Name",
                "width": 160,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 100},
            {"field": "releaseDate", "headerName": "Release Date"},
        ]
        self.all_creature_types = self.load_types(all_creature_types_file)
        self.all_land_types = self.load_types(all_land_types_file)
        self.nonbasic_land_types = self.all_land_types - BASIC_LAND_TYPES

    def load_types(self, file_path: Path) -> Set[str]:
        """Load types from a text file."""
        try:
            with file_path.resolve().open("r") as f:
                return set(line.strip() for line in f if line.strip())
        except IOError as e:
            logger.error(f"Failed to load types from {file_path}: {e}")
            return set()

    def process_card(self, card: Dict[str, Any]) -> None:
        if not is_traditional_card(card):
            return

        if "card_faces" in card:
            for face in card["card_faces"]:
                self.process_single_face(face, card)
        else:
            self.process_single_face(card, card)

    def process_single_face(
        self, face: Dict[str, Any], parent_card: Dict[str, Any]
    ) -> None:
        """Process a single face of a card."""
        card_types = extract_types(face)

        if "Token" in card_types or "Emblem" in card_types:
            return

        if is_all_creature_types(face):
            card_types |= self.all_creature_types

        if face.get("name") == "Planar Nexus":
            card_types |= self.nonbasic_land_types

        type_key = tuple(sorted(card_types))

        if type_key in self.maximal_types:
            existing_card = self.maximal_types[type_key]
            if get_sort_key(parent_card) < get_sort_key(existing_card):
                self.maximal_types[type_key] = parent_card
            return

        is_maximal = all(
            not set(type_key).issubset(set(existing_key))
            for existing_key in self.maximal_types.keys()
        )

        if is_maximal:
            keys_to_remove = [
                existing_key
                for existing_key in self.maximal_types.keys()
                if set(existing_key).issubset(set(type_key))
            ]
            for key in keys_to_remove:
                del self.maximal_types[key]
            self.maximal_types[type_key] = parent_card

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {
                "types": card.get("type_line", ""),
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
                "scryfall_uri": card.get("scryfall_uri", ""),
                "image_uri": (
                    card.get("image_uris", {}).get("normal", "")
                    if card.get("image_uris")
                    else ""
                ),
            }
            for key, card in sorted(
                self.maximal_types.items(), key=lambda item: get_sort_key(item[1])
            )
        ]


class MaximalTypesWithEffectsAggregator(MaximalPrintedTypesAggregator):
    """Find cards with maximal types considering global effects."""

    def __init__(
        self,
        all_creature_types_file: Path,
        all_land_types_file: Path,
        description: str = "",
    ):
        super().__init__(all_creature_types_file, all_land_types_file, description)
        self.name = "maximal_types_with_effects"
        self.display_name = "Maximal Types with Global Effects"
        self.description = "Cards with maximal types, considering global effects"
        self.explanation = """
## What are Maximal Types with Global Effects?

This report shows cards that achieve the maximum number of types when considering **global effects**
from other cards that could be in play simultaneously.

Unlike "Maximal Printed Types" which only counts what's printed on the card, this aggregator
considers how cards would be modified by other permanents in play.

## Global Effects Considered

The following cards and their effects are included in the calculation:

**Type-Granting Effects:**
- **In Bolas's Clutches** - Makes permanents Legendary
- **Rimefeather Owl** - Makes permanents Snow
- **Enchanted Evening** - Makes permanents Enchantments
- **Mycosynth Lattice** - Makes permanents Artifacts
- **March of the Machines** - Makes artifacts into Creatures

**Creature Type Effects:**
- **Maskwood Nexus** - Creatures have all creature types
- **Cards with Changeling** - Already have all creature types

**Land Type Effects:**
- **Life and Limb** - Forests and Saprolings become Creature Land Saproling Forest
- **Prismatic Omen** - Lands have all basic land types
- **Planar Nexus** - Has all nonbasic land types
- **Omo, Queen of Vesuva** - Lands have all land types, Creatures have all creature types

This shows the theoretical maximum types achievable through card combinations!

**Important note:**
- **Type lag:** There may be a delay between when new creature or land types appear on cards and when they're officially added to the comprehensive rules. Cards that grant "all creature types" or "all land types" will only include types that have been updated via the `update-types` command, which fetches the official type lists from the comprehensive rules
        """
        self.global_effects = self.define_global_effects()
        self.maximal_types: Dict[Tuple[str, ...], Tuple[Dict[str, Any], Set[str]]] = {}
        self.column_defs = [
            {"field": "originalTypes", "headerName": "Original Types", "width": 240},
            {
                "field": "name",
                "headerName": "Name",
                "width": 160,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 100},
            {"field": "releaseDate", "headerName": "Release Date"},
        ]

    def define_global_effects(self):
        """Define global effects that modify card types."""
        return {
            "In Bolas's Clutches": lambda card_types: card_types.union({"Legendary"})
            if is_permanent({"type_line": " ".join(card_types)})
            else card_types,
            "Rimefeather Owl": lambda card_types: card_types.union({"Snow"})
            if is_permanent({"type_line": " ".join(card_types)})
            else card_types,
            "Enchanted Evening": lambda card_types: card_types.union({"Enchantment"})
            if is_permanent({"type_line": " ".join(card_types)})
            else card_types,
            "Mycosynth Lattice": lambda card_types: card_types.union({"Artifact"})
            if is_permanent({"type_line": " ".join(card_types)})
            else card_types,
            "March of the Machines": lambda card_types: card_types.union({"Creature"})
            if "Artifact" in card_types and "Creature" not in card_types
            else card_types,
            "Maskwood Nexus": lambda card_types: card_types.union(
                self.all_creature_types
            )
            if "Creature" in card_types
            else card_types,
            "Life and Limb": lambda card_types: card_types.union(
                {"Creature", "Land", "Saproling", "Forest"}
            )
            if "Forest" in card_types or "Saproling" in card_types
            else card_types,
            "Prismatic Omen": lambda card_types: card_types.union(BASIC_LAND_TYPES)
            if "Land" in card_types
            else card_types,
            "Omo, Queen of Vesuva": lambda card_types: card_types.union(
                BASIC_LAND_TYPES, self.nonbasic_land_types
            )
            if "Land" in card_types
            else card_types.union(self.all_creature_types)
            if "Creature" in card_types
            else card_types,
        }

    def apply_global_effects(self, card_types: Set[str]) -> Set[str]:
        """Apply all global effects to the card types."""
        for effect in self.global_effects.values():
            card_types = effect(card_types)
        return card_types

    def process_single_face(
        self, face: Dict[str, Any], parent_card: Dict[str, Any]
    ) -> None:
        """Process a single face with global effects applied."""
        card_types = extract_types(face)

        if "Token" in card_types or "Emblem" in card_types:
            return

        if is_all_creature_types(face):
            card_types |= self.all_creature_types

        if face.get("name") == "Planar Nexus":
            card_types |= self.nonbasic_land_types

        # Apply global effects
        card_types = self.apply_global_effects(card_types)

        type_key = tuple(sorted(card_types))

        if type_key in self.maximal_types:
            existing_card = self.maximal_types[type_key]
            if get_sort_key(parent_card) < get_sort_key(existing_card):
                self.maximal_types[type_key] = parent_card
            return

        is_maximal = all(
            not set(type_key).issubset(set(existing_key))
            for existing_key in self.maximal_types.keys()
        )

        if is_maximal:
            keys_to_remove = [
                existing_key
                for existing_key in self.maximal_types.keys()
                if set(existing_key).issubset(set(type_key))
            ]
            for key in keys_to_remove:
                del self.maximal_types[key]
            self.maximal_types[type_key] = parent_card

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {
                "originalTypes": card.get("type_line", ""),
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
                "scryfall_uri": card.get("scryfall_uri", ""),
                "image_uri": (
                    card.get("image_uris", {}).get("normal", "")
                    if card.get("image_uris")
                    else ""
                ),
            }
            for key, card in sorted(
                self.maximal_types.items(), key=lambda item: get_sort_key(item[1])
            )
        ]
