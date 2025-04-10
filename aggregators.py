import json
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from jinja2 import Template

from card_utils import (
    BASIC_LAND_TYPES,
    extract_types,
    generalize_mana_cost,
    get_sort_key,
    is_all_creature_types,
    is_permanent,
    is_traditional_card,
)

# Constants
NON_TRADITIONAL_SET_TYPES = {"memorabilia", "funny"}
NON_TRADITIONAL_LAYOUTS = {"emblem", "token"}
NON_TRADITIONAL_BORDERS = {"silver", "gold"}
FOIL_PROMO_TYPES = {
    "confettifoil",
    "doublerainbow",
    "embossed",
    "galaxyfoil",
    "gilded",
    "halofoil",
    "invisibleink",
    "neonink",
    "oilslick",
    "rainbowfoil",
    "raisedfoil",
    "ripplefoil",
    "silverfoil",
    "stepandcompleat",
    "surgefoil",
    "textured",
}
MODERN_FOIL_CUTOFF_DATE = datetime(2003, 7, 28)  # Release date of 8th Edition
SPECIAL_FOIL_SETS = {
    "mps": "inventions",  # Kaladesh Inventions
    "mp2": "invocations",  # Amonkhet Invocations
    "exp": "expedition",  # Zendikar Expeditions
    "psus": "sunburst",  # Junior Super Series promos
    "dbl": "silverscreen",  # Innistrad Double Feature
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Aggregator(ABC):
    def __init__(self, name: str, display_name: str, description: str = ""):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.column_defs = []

    @abstractmethod
    def process_card(self, card: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_sorted_data(
        self,
    ) -> List[Dict[str, Any]]:  # Changed to return dict for ag-grid
        pass

    def generate_html_file(
        self, output_folder: Path, template: Template, nav_links: List[Dict[str, str]]
    ) -> None:
        # Generate JSON file
        json_filename = f"{self.name}.json"
        json_filepath = output_folder / json_filename
        with json_filepath.open("w", encoding="utf-8") as json_file:
            json.dump(self.get_sorted_data(), json_file)

        # Generate HTML file using template
        html_content = template.render(
            title=self.display_name,
            display_name=self.display_name,
            description=self.description,
            nav_links=nav_links,
            data_file=json_filename,
            column_defs=self.column_defs,
        )

        output_file = output_folder / f"{self.name}.html"
        with output_file.open("w", encoding="utf-8") as f:
            f.write(html_content)


class CountAggregator(Aggregator):
    def __init__(
        self,
        name: str,
        display_name: str,
        key_fields: List[str],
        count_finishes: bool = False,
        description: str = "",
    ):
        super().__init__(name, display_name, description)
        self.data: Dict[Tuple, int] = defaultdict(int)
        self.key_fields = key_fields
        self.count_finishes = count_finishes

        # Define column definitions for ag-grid
        self.column_defs = [
            {"field": field, "headerName": field.title()} for field in key_fields
        ]
        self.column_defs.append(
            {"field": "count", "headerName": "Count", "type": "numericColumn"}
        )

    def process_card(self, card: Dict[str, Any]) -> None:
        key = tuple(card.get(field) for field in self.key_fields)
        self.data[key] += len(card.get("finishes", [])) if self.count_finishes else 1

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        # Return data in format suitable for ag-grid
        return sorted(
            [
                {**dict(zip(self.key_fields, key)), "count": count}
                for key, count in self.data.items()
            ],
            key=lambda x: x["count"],
            reverse=True,
        )


class MaxCollectorNumberBySetAggregator(Aggregator):
    def __init__(self, description: str = ""):
        super().__init__(
            "max_collector_number_by_set",
            "Maximum Collector Number by Set",
            description,
        )
        self.data: Dict[str, int] = defaultdict(int)
        self.column_defs = [
            {"field": "set", "headerName": "Set", "width": 100},
            {
                "field": "maxNumber",
                "headerName": "Max Collector Number",
                "type": "numericColumn",
                "sort": "desc",
            },
        ]

    def process_card(self, card: Dict[str, Any]) -> None:
        collector_number = card.get("collector_number")
        if collector_number is not None and collector_number.isdigit():
            key = card.get("set")
            collector_number = int(collector_number)
            self.data[key] = max(self.data[key], collector_number)

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {"set": key, "maxNumber": value}
            for key, value in sorted(
                self.data.items(), key=lambda x: x[1], reverse=True
            )
        ]


class CountCardIllustrationsBySetAggregator(Aggregator):
    def __init__(self, description: str = ""):
        super().__init__(
            "count_card_illustrations_by_set",
            "Card Illustrations Count by Set",
            description,
        )
        self.data: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        self.column_defs = [
            {"field": "set", "headerName": "Set"},
            {"field": "name", "headerName": "Name"},
            {
                "field": "count",
                "headerName": "Count",
                "type": "numericColumn",
                "sort": "desc",
            },
        ]

    def process_card(self, card: Dict[str, Any]) -> None:
        key = (card.get("set"), card.get("name"))
        self.data[key].add(card.get("illustration_id"))

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {"set": set_, "name": name, "count": len(illustrations)}
            for (set_, name), illustrations in self.data.items()
        ]


class MaximalPrintedTypesAggregator(Aggregator):
    def __init__(
        self,
        all_creature_types_file: Path,
        all_land_types_file: Path,
        description: str = "",
    ):
        super().__init__("maximal_printed_types", "Maximal Printed Types", description)
        self.maximal_types: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        self.column_defs = [
            {"field": "types", "headerName": "Types", "width": 240},
            {"field": "name", "headerName": "Name", "width": 160},
            {"field": "set", "headerName": "Set", "width": 100},
            {"field": "releaseDate", "headerName": "Release Date"},
        ]
        self.all_creature_types = self.load_types(all_creature_types_file)
        self.all_land_types = self.load_types(all_land_types_file)
        self.nonbasic_land_types = self.all_land_types - BASIC_LAND_TYPES

    def load_types(self, file_path: Path) -> Set[str]:
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
        """
        Process a single face of a card, updating maximal types if necessary.

        Args:
            face: The face of the card being processed.
            parent_card: The full card data, used for metadata.
        """
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
            }
            for key, card in sorted(
                self.maximal_types.items(), key=lambda item: get_sort_key(item[1])
            )
        ]


class PromoTypesAggregator(Aggregator):
    def __init__(self, description: str = ""):
        super().__init__("promo_types_by_name", "Promo Types by Card Name", description)
        self.data: Dict[str, Set[str]] = defaultdict(set)
        self.column_defs = [
            {"field": "name", "headerName": "Name", "width": 160},
            {"field": "promoTypes", "headerName": "Promo Types", "width": 320},
            {
                "field": "count",
                "headerName": "Count",
                "type": "numericColumn",
                "sort": "desc",
            },
        ]

    def process_card(self, card: Dict[str, Any]) -> None:
        name = card.get("name")
        promo_types = card.get("promo_types", [])
        if promo_types:
            self.data[name].update(promo_types)

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "promoTypes": ", ".join(sorted(promo_types)),
                "count": len(promo_types),
            }
            for name, promo_types in self.data.items()
        ]


class FirstCardByPowerToughnessAggregator(Aggregator):
    def __init__(self, description: str = ""):
        super().__init__(
            "first_card_by_power_toughness",
            "First Cards by Power and Toughness",
            description,
        )
        self.data: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.column_defs = [
            {"field": "power", "headerName": "Power", "width": 100},
            {"field": "toughness", "headerName": "Toughness", "width": 100},
            {"field": "name", "headerName": "Name", "width": 200},
            {"field": "set", "headerName": "Set", "width": 100},
            {"field": "releaseDate", "headerName": "Release Date", "width": 150},
        ]

    def process_card(self, card: Dict[str, Any]) -> None:
        power = card.get("power", "")
        toughness = card.get("toughness", "")

        if power == "" or toughness == "":
            return

        key = (power, toughness)

        if key not in self.data or get_sort_key(card) < get_sort_key(self.data[key]):
            self.data[key] = card

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {
                "power": power,
                "toughness": toughness,
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
            }
            for (power, toughness), card in sorted(
                self.data.items(), key=lambda item: get_sort_key(item[1])
            )
        ]


class FoilTypesAggregator(Aggregator):
    def __init__(self, description: str = ""):
        super().__init__("foil_types_by_name", "Foil Types by Card Name", description)
        self.data: Dict[str, Set[str]] = defaultdict(set)
        self.column_defs = [
            {"field": "name", "headerName": "Name", "width": 200},
            {"field": "foilTypes", "headerName": "Foil Types", "width": 400},
            {
                "field": "count",
                "headerName": "Count",
                "type": "numericColumn",
                "sort": "desc",
            },
        ]

    def process_card(self, card: Dict[str, Any]) -> None:
        name = card.get("name")
        set_ = card.get("set")

        # Handle special foil sets (Inventions, Invocations, Expeditions, Junior Super Series)
        if set_ in SPECIAL_FOIL_SETS:
            self.data[name].add(SPECIAL_FOIL_SETS[set_])
            return  # Exit early as these cards have their own unique foil type

        # Filter promo types for actual foil types
        promo_types = card.get("promo_types", [])
        if promo_types:
            self.data[name].update(p for p in promo_types if p in FOIL_PROMO_TYPES)

        # From the Vault have their own foil type
        set_type = card.get("set_type")
        if set_type == "from_the_vault":
            self.data[name].add("from_the_vault")

        # TODO: handle SDCC planeswalkers

        # Calculate which era of traditional foil applies
        # TODO: still need to better differentiate types of traditional foils:
        # e.g. retro frame foils, M15 and prior cards that have spot foiling in the art
        finishes = card.get("finishes", [])
        if "foil" in finishes:
            release_date_str = card.get("released_at")
            if release_date_str:
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d")
                if release_date < MODERN_FOIL_CUTOFF_DATE:
                    self.data[name].add("premodern_foil")
                else:
                    self.data[name].add("modern_foil")
            else:
                # If no release date is available, assume it's modern foil
                self.data[name].add("modern_foil")

        # Check for etched finish
        if "etched" in finishes:
            self.data[name].add("etched")

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "foilTypes": ", ".join(sorted(foil_types)),
                "count": len(foil_types),
            }
            for name, foil_types in self.data.items()
        ]


def format_time_difference(days: int) -> str:
    years, remaining_days = divmod(days, 365)
    months, days = divmod(remaining_days, 30)

    parts = []
    if years > 0:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months > 0:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")

    return ", ".join(parts)


class SupercycleTimeAggregator(Aggregator):
    def __init__(self, supercycles_file: Path, description: str = ""):
        super().__init__(
            "supercycle_completion_time", "Supercycle Completion Times", description
        )
        self.supercycles = self.load_supercycles(supercycles_file)
        self.card_dates: Dict[str, date] = {}
        self.column_defs = [
            {"field": "supercycle", "headerName": "Supercycle", "width": 200},
            {"field": "status", "headerName": "Status", "width": 120},
            {"field": "time", "headerName": "Time", "width": 200},
            {"field": "startDate", "headerName": "Start Date", "width": 150},
            {"field": "endDate", "headerName": "End Date", "width": 150},
        ]

    def load_supercycles(self, file_path: Path) -> Dict[str, Dict[str, Any]]:
        try:
            with file_path.open("r") as f:
                data = json.load(f)
                return {cycle["name"]: cycle for cycle in data["supercycles"]}
        except IOError as e:
            logger.error(f"Failed to load supercycles from {file_path}: {e}")
            return {}

    def process_card(self, card: Dict[str, Any]) -> None:
        name = card.get("name")
        released_at = card.get("released_at")
        if name and released_at:
            card_date = date.fromisoformat(released_at)
            if name not in self.card_dates or card_date < self.card_dates[name]:
                self.card_dates[name] = card_date

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        today = date.today()
        result = []

        for name, cycle in self.supercycles.items():
            card_dates = [
                self.card_dates.get(card)
                for card in cycle["cards"]
                if card in self.card_dates
            ]
            if not card_dates:
                continue

            earliest_date = min(card_dates)
            if cycle["finished"]:
                latest_date = max(card_dates)
            else:
                latest_date = today

            days = (latest_date - earliest_date).days
            status = "Finished" if cycle["finished"] else "Unfinished"
            formatted_time = format_time_difference(days)
            result.append(
                {
                    "supercycle": name,
                    "status": status,
                    "time": formatted_time,
                    "startDate": earliest_date.strftime("%B %d, %Y"),
                    "endDate": latest_date.strftime("%B %d, %Y")
                    if cycle["finished"]
                    else "Ongoing",
                }
            )

        return sorted(result, key=lambda x: int(x["time"].split()[0]), reverse=True)


class MaximalTypesWithEffectsAggregator(MaximalPrintedTypesAggregator):
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
        self.global_effects = self.define_global_effects()
        self.maximal_types: Dict[Tuple[str, ...], Tuple[Dict[str, Any], Set[str]]] = {}
        self.column_defs = [
            {"field": "originalTypes", "headerName": "Original Types", "width": 240},
            {"field": "name", "headerName": "Name", "width": 160},
            {"field": "set", "headerName": "Set", "width": 100},
            {"field": "releaseDate", "headerName": "Release Date"},
        ]

    def define_global_effects(self):
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
        for effect in self.global_effects.values():
            card_types = effect(card_types)
        return card_types

    def process_single_face(
        self, face: Dict[str, Any], parent_card: Dict[str, Any]
    ) -> None:
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
            }
            for key, card in sorted(
                self.maximal_types.items(), key=lambda item: get_sort_key(item[1])
            )
        ]


class FirstCardByGeneralizedManaCostAggregator(Aggregator):
    def __init__(self, description: str = ""):
        super().__init__(
            "first_card_by_generalized_mana_cost",
            "First Cards by Generalized Mana Cost",
            description,
        )
        self.data: Dict[str, Dict[str, Any]] = {}
        self.count: Dict[str, int] = defaultdict(int)
        self.column_defs = [
            {
                "field": "generalizedManaCost",
                "headerName": "Generalized Mana Cost",
                "width": 120,
            },
            {"field": "name", "headerName": "Name", "width": 200},
            {"field": "set", "headerName": "Set", "width": 100},
            {"field": "releaseDate", "headerName": "Release Date", "width": 150},
            {
                "field": "originalManaCost",
                "headerName": "Original Mana Cost",
                "width": 150,
            },
            {"field": "count", "headerName": "Count", "type": "numericColumn"},
        ]

    def process_card(self, card: Dict[str, Any]) -> None:
        mana_cost = card.get("mana_cost")
        if mana_cost:
            generalized_cost = generalize_mana_cost(mana_cost)
            self.count[generalized_cost] += 1
            if generalized_cost not in self.data or get_sort_key(card) < get_sort_key(
                self.data[generalized_cost]
            ):
                self.data[generalized_cost] = card

    def get_sorted_data(self) -> List[Dict[str, Any]]:
        return [
            {
                "generalizedManaCost": generalized_cost,
                "name": card.get("name", ""),
                "set": card.get("set", ""),
                "releaseDate": card.get("released_at", ""),
                "originalManaCost": card.get("mana_cost", ""),
                "count": self.count[generalized_cost],
            }
            for generalized_cost, card in sorted(
                self.data.items(), key=lambda item: get_sort_key(item[1])
            )
        ]
