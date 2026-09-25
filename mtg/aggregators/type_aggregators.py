"""Aggregators for analyzing card types."""

from typing import Any

from mtg.card import Card, Face
from mtg.card_utils import BASIC_LAND_TYPES, extract_types, is_permanent

from .base import Aggregator, AggregatorContext, card_columns, card_fields

# Card types whose subtypes are creature or land types, and therefore verifiable
# against the comprehensive rules type lists.
SUBTYPE_VERIFIABLE_TYPES = {"Creature", "Kindred", "Tribal", "Land"}

# Types marking non-playable objects: Tokens and Emblems aren't cards, while
# "Card" and "Stickers" are Scryfall placeholders for substitute cards, art
# series, sticker sheets, and similar objects.
SKIPPED_TYPES = {"Token", "Emblem", "Card", "Stickers"}


class MaximalPrintedTypesAggregator(Aggregator):
    """Find cards with maximal printed type combinations."""

    name = "maximal_printed_types"
    display_name = "Maximal Printed Types"
    description = "Cards with maximal printed types"
    explanation = (
        "Cards whose printed types form a maximum set: no other card's printed types"
        " are a strict superset. Changelings count as having all creature types,"
        " Planar Nexus counts as having all nonbasic land types, and Grist counts as"
        " an Insect creature. Cards with creature or"
        " land subtypes that are not yet in the comprehensive rules (e.g. from newly"
        " previewed sets) are excluded until the rules are updated."
    )
    traditional_only = True
    # Row field holding the card's printed type line.
    types_field = "types"
    column_defs = [
        {"field": "types", "headerName": "Types", "width": 300},
        *card_columns("Name"),
    ]
    type_filters = [
        {"field": "types", "label": "Planes", "keyword": "Plane"},
        {"field": "types", "label": "Planeswalkers", "keyword": "Planeswalker"},
    ]

    def __init__(self, context: AggregatorContext | None = None):
        super().__init__(context)
        type_lists = self.context.type_lists
        if not type_lists.loaded:
            self.warnings.append(
                "Creature/land types not loaded; run `mtg update-types`."
                " Unknown subtypes can't be detected."
            )
        # Maps a type set to the (face, card) pair that produced it.
        self.maximal_types: dict[frozenset[str], tuple[Face, Card]] = {}
        self._unknown_subtypes_seen: set[str] = set()
        self.all_creature_types = type_lists.creature
        self.all_land_types = type_lists.land
        self.non_creature_land_subtypes = type_lists.non_creature_land_subtypes
        self.nonbasic_land_types = self.all_land_types - BASIC_LAND_TYPES

    def process_card(self, card: Card) -> None:
        for face in card.faces:
            self.process_single_face(face, card)

    def process_single_face(self, face: Face, parent_card: Card) -> None:
        """Process a single face of a card."""
        card_types = set(face.types)

        if card_types & SKIPPED_TYPES:
            return

        unknown_subtypes = self._get_unknown_subtypes(face, card_types)
        if unknown_subtypes:
            for subtype in sorted(unknown_subtypes):
                if subtype not in self._unknown_subtypes_seen:
                    self._unknown_subtypes_seen.add(subtype)
                    self.warnings.append(
                        f"Skipping cards with subtype '{subtype}'"
                        f" (e.g. {face.name or 'Unknown'}):"
                        " not yet in the comprehensive rules type lists"
                    )
            return

        if face.is_all_creature_types:
            card_types |= self.all_creature_types

        if face.name == "Planar Nexus":
            card_types |= self.nonbasic_land_types

        # Grist is a 1/1 Insect creature in every zone except the battlefield.
        if face.name == "Grist, the Hunger Tide":
            card_types |= {"Creature", "Insect"}

        card_types = self._modify_types(card_types)

        type_key = frozenset(card_types)

        if type_key in self.maximal_types:
            _existing_face, existing_card = self.maximal_types[type_key]
            if parent_card.sort_key < existing_card.sort_key:
                self.maximal_types[type_key] = (face, parent_card)
            return

        if any(type_key < existing_key for existing_key in self.maximal_types):
            return

        for key in [k for k in self.maximal_types if k < type_key]:
            del self.maximal_types[key]
        self.maximal_types[type_key] = (face, parent_card)

    def _get_unknown_subtypes(self, face: Face, card_types: set[str]) -> set[str]:
        """
        Find creature/land subtypes on a face that aren't in the comprehensive rules yet.

        Scryfall publishes card data for newly previewed sets before the comprehensive
        rules (and thus the type lists) are updated, which would otherwise produce
        spurious maximal rows. Only creature and land subtypes can be verified;
        known artifact, enchantment, and spell subtypes sharing the type line (e.g.
        the Saga in "Enchantment Land — Urza's Saga") are allowed through.
        """
        if not self.all_creature_types or not self.all_land_types:
            # Type lists aren't loaded; __init__ already warned.
            return set()
        if not card_types & SUBTYPE_VERIFIABLE_TYPES:
            return set()
        if "—" not in face.type_line:
            return set()
        subtypes = extract_types({"type_line": face.type_line.split("—", 1)[1]})
        return (
            subtypes
            - self.all_creature_types
            - self.all_land_types
            - self.non_creature_land_subtypes
        )

    def _modify_types(self, card_types: set[str]) -> set[str]:
        """Hook for subclasses to modify types before maximality check."""
        return card_types

    def get_sorted_data(self) -> list[dict[str, Any]]:
        return [
            {self.types_field: card.type_line, **card_fields(card, face)}
            for face, card in sorted(self.maximal_types.values(), key=lambda pair: pair[1].sort_key)
        ]


class MaximalTypesWithEffectsAggregator(MaximalPrintedTypesAggregator):
    """Find cards with maximal types considering global effects."""

    name = "maximal_types_with_effects"
    display_name = "Maximal Types with Global Effects"
    description = "Cards with maximal types, considering global effects"
    explanation = (
        "Cards that reach the maximum number of types when global effects from other cards"
        " in play are applied (e.g., In Bolas's Clutches grants Legendary, Maskwood Nexus"
        " grants all creature types, Ashaya makes creatures Forest lands, Omo grants all"
        " land and creature types). Cards with"
        " creature or land subtypes that are not yet in the comprehensive rules (e.g. from"
        " newly previewed sets) are excluded until the rules are updated."
    )
    types_field = "originalTypes"
    column_defs = [
        {"field": "originalTypes", "headerName": "Original Types", "width": 300},
        *card_columns("Name"),
    ]
    type_filters = [
        {"field": "originalTypes", "label": "Planes", "keyword": "Plane"},
        {"field": "originalTypes", "label": "Planeswalkers", "keyword": "Planeswalker"},
    ]

    def __init__(self, context: AggregatorContext | None = None):
        super().__init__(context)
        self.global_effects = self._define_global_effects()

    def _omo_effect(self, card_types: set[str]) -> set[str]:
        """Omo grants all land types to Lands, all creature types to Creatures."""
        if "Land" in card_types:
            return card_types.union(BASIC_LAND_TYPES, self.nonbasic_land_types)
        if "Creature" in card_types:
            return card_types.union(self.all_creature_types)
        return card_types

    def _define_global_effects(self):
        """
        Define global effects that modify card types.

        Keep this list minimal: an effect belongs here only if it grants a type
        no combination of the other effects can reach (e.g. Life and Limb and
        Prismatic Omen were removed once Ashaya and Omo covered their grants).
        """
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
            "Ragost, Deft Gastronaut": lambda card_types: card_types.union({"Food"})
            if "Artifact" in card_types
            else card_types,
            "Senator Peacock": lambda card_types: card_types.union({"Clue"})
            if "Artifact" in card_types
            else card_types,
            "Armed with Proof": lambda card_types: card_types.union({"Equipment"})
            if "Clue" in card_types
            else card_types,
            "March of the Machines": lambda card_types: card_types.union({"Creature"})
            if "Artifact" in card_types and "Creature" not in card_types
            else card_types,
            "Maskwood Nexus": lambda card_types: card_types.union(self.all_creature_types)
            if "Creature" in card_types
            else card_types,
            "Ashaya, Soul of the Wild": lambda card_types: card_types.union({"Land", "Forest"})
            if "Creature" in card_types
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
