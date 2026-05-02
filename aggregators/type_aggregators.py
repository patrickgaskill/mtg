"""Aggregators for analyzing card types."""

from pathlib import Path
from typing import Any

from card_utils import (
    BASIC_LAND_TYPES,
    extract_types,
    get_card_link_data,
    get_sort_key,
    is_all_creature_types,
    is_permanent,
    is_traditional_card,
)

from .base import Aggregator


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
            explanation=(
                "Cards whose printed types form a maximum set — no other card's printed types"
                " are a strict superset. Changelings count as having all creature types and"
                " Planar Nexus counts as having all nonbasic land types."
            ),
        )
        self.maximal_types: dict[tuple[str, ...], dict[str, Any]] = {}
        self._types_field = "types"
        self.column_defs = [
            {"field": "types", "headerName": "Types", "width": 300},
            {
                "field": "name",
                "headerName": "Name",
                "width": 200,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 80},
            {"field": "releaseDate", "headerName": "Release Date", "width": 120},
        ]
        self.type_filters = [
            {"field": "types", "label": "Planes", "keyword": "Plane"},
            {"field": "types", "label": "Planeswalkers", "keyword": "Planeswalker"},
        ]
        self.all_creature_types = self.load_types(all_creature_types_file)
        self.all_land_types = self.load_types(all_land_types_file)
        self.nonbasic_land_types = self.all_land_types - BASIC_LAND_TYPES

    def load_types(self, file_path: Path) -> set[str]:
        """Load types from a text file."""
        try:
            with file_path.resolve().open("r") as f:
                return {line.strip() for line in f if line.strip()}
        except OSError as e:
            self.warnings.append(f"Error: Failed to load types from {file_path}: {e}")
            return set()

    def process_card(self, card: dict[str, Any]) -> None:
        if not is_traditional_card(card):
            return

        if "card_faces" in card:
            for face in card["card_faces"]:
                self.process_single_face(face, card)
        else:
            self.process_single_face(card, card)

    def process_single_face(self, face: dict[str, Any], parent_card: dict[str, Any]) -> None:
        """Process a single face of a card."""
        card_types = extract_types(face)

        if "Token" in card_types or "Emblem" in card_types:
            return

        if is_all_creature_types(face):
            card_types |= self.all_creature_types

        if face.get("name") == "Planar Nexus":
            card_types |= self.nonbasic_land_types

        card_types = self._modify_types(card_types)

        type_key = tuple(sorted(card_types))

        if type_key in self.maximal_types:
            existing_card = self.maximal_types[type_key]
            if get_sort_key(parent_card) < get_sort_key(existing_card):
                self.maximal_types[type_key] = parent_card
            return

        is_maximal = all(
            not set(type_key).issubset(set(existing_key)) for existing_key in self.maximal_types
        )

        if is_maximal:
            keys_to_remove = [
                existing_key
                for existing_key in self.maximal_types
                if set(existing_key).issubset(set(type_key))
            ]
            for key in keys_to_remove:
                del self.maximal_types[key]
            self.maximal_types[type_key] = parent_card

    def _modify_types(self, card_types: set[str]) -> set[str]:
        """Hook for subclasses to modify types before maximality check."""
        return card_types

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {
                self._types_field: card.get("type_line", ""),
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
                **get_card_link_data(card),
            }
            for _key, card in sorted(
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
        self.explanation = (
            "Cards that reach the maximum number of types when global effects from other cards"
            " in play are applied (e.g., In Bolas's Clutches grants Legendary, Maskwood Nexus"
            " grants all creature types, Omo grants all land and creature types)."
        )
        self._types_field = "originalTypes"
        self.global_effects = self._define_global_effects()
        self.maximal_types: dict[tuple[str, ...], dict[str, Any]] = {}
        self.column_defs = [
            {"field": "originalTypes", "headerName": "Original Types", "width": 300},
            {
                "field": "name",
                "headerName": "Name",
                "width": 200,
                "cellRenderer": "cardLinkRenderer",
            },
            {"field": "set", "headerName": "Set", "width": 80},
            {"field": "releaseDate", "headerName": "Release Date", "width": 120},
        ]
        self.type_filters = [
            {"field": "originalTypes", "label": "Planes", "keyword": "Plane"},
            {"field": "originalTypes", "label": "Planeswalkers", "keyword": "Planeswalker"},
        ]

    def _omo_effect(self, card_types: set[str]) -> set[str]:
        """Omo grants all land types to Lands, all creature types to Creatures."""
        if "Land" in card_types:
            return card_types.union(BASIC_LAND_TYPES, self.nonbasic_land_types)
        if "Creature" in card_types:
            return card_types.union(self.all_creature_types)
        return card_types

    def _define_global_effects(self):
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
            "Maskwood Nexus": lambda card_types: card_types.union(self.all_creature_types)
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
            "Omo, Queen of Vesuva": self._omo_effect,
        }

    def _apply_global_effects(self, card_types: set[str]) -> set[str]:
        """Apply all global effects to the card types."""
        for effect in self.global_effects.values():
            card_types = effect(card_types)
        return card_types

    def _modify_types(self, card_types: set[str]) -> set[str]:
        return self._apply_global_effects(card_types)
