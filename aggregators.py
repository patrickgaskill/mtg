import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from jinja2 import Template

from card_utils import (
    BASIC_LAND_TYPES,
    extract_types,
    get_sort_key,
    is_all_creature_types,
    is_traditional_card,
)

# Constants
NON_TRADITIONAL_SET_TYPES = {"memorabilia", "funny"}
NON_TRADITIONAL_LAYOUTS = {"emblem", "token"}
NON_TRADITIONAL_BORDERS = {"silver", "gold"}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Aggregator(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def process_card(self, card: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_sorted_data(self) -> List[List[Any]]:
        pass

    def generate_html_file(
        self, output_folder: Path, template: Template, nav_links: List[Dict[str, str]]
    ) -> None:
        output_file = output_folder / f"{self.name}.html"

        sorted_data = self.get_sorted_data()

        html_content = template.render(
            name=self.name,
            column_names=self.column_names,
            column_widths=self.column_widths,
            items=sorted_data,
            nav_links=nav_links,
        )

        try:
            with output_file.open("w", encoding="utf-8") as f:
                f.write(html_content)
        except IOError as e:
            logger.error(f"Failed to write HTML file {output_file}: {e}")


class CountAggregator(Aggregator):
    def __init__(
        self,
        name: str,
        key_fields: List[str],
        count_finishes: bool = False,
        description: str = "",
    ):
        super().__init__(name, description)
        self.data: Dict[Tuple, int] = defaultdict(int)
        self.key_fields = key_fields
        self.count_finishes = count_finishes
        self.column_names = key_fields + ["Count"]
        self.column_widths = ["8rem"] * len(key_fields) + ["4rem"]

    def process_card(self, card: Dict[str, Any]) -> None:
        key = tuple(card.get(field) for field in self.key_fields)
        self.data[key] += len(card.get("finishes", [])) if self.count_finishes else 1

    def get_sorted_data(self) -> List[List[Any]]:
        return sorted(
            [list(key) + [count] for key, count in self.data.items()],
            key=lambda x: x[-1],
            reverse=True,
        )


class MaxCollectorNumberBySetAggregator(Aggregator):
    def __init__(self, description: str = ""):
        super().__init__("max_collector_number_by_set", description)
        self.data: Dict[str, int] = defaultdict(int)
        self.column_names = ["Set", "Max Collector Number"]
        self.column_widths = ["4rem", "10rem"]

    def process_card(self, card: Dict[str, Any]) -> None:
        collector_number = card.get("collector_number")
        if collector_number is not None and collector_number.isdigit():
            key = card.get("set")
            collector_number = int(collector_number)
            self.data[key] = max(self.data[key], collector_number)

    def get_sorted_data(self) -> List[List[Any]]:
        return sorted(
            [[key, value] for key, value in self.data.items()],
            key=lambda x: x[1],
            reverse=True,
        )


class CountCardIllustrationsBySetAggregator(Aggregator):
    def __init__(self, description: str = ""):
        super().__init__("count_card_illustrations_by_set", description)
        self.data: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        self.column_names = ["Set", "Name", "Count"]
        self.column_widths = ["4rem", "8rem", "4rem"]

    def process_card(self, card: Dict[str, Any]) -> None:
        key = (card.get("set"), card.get("name"))
        self.data[key].add(card.get("illustration_id"))

    def get_sorted_data(self) -> List[Tuple[Tuple[str, str], int]]:
        return sorted(
            [[key, len(illustrations)] for key, illustrations in self.data.items()],
            key=lambda item: item[1],
            reverse=True,
        )


class MaximalPrintedTypesAggregator(Aggregator):
    def __init__(
        self,
        all_creature_types_file: Path,
        all_land_types_file: Path,
        description: str = "",
    ):
        super().__init__("maximal_printed_types", description)
        self.maximal_types: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        self.column_names = ["Types", "Name", "Set", "Release Date"]
        self.column_widths = ["24rem", "16rem", "4rem", "4rem"]
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

    def get_sorted_data(self) -> List[Tuple[Tuple[str, str, str], str]]:
        return [
            [
                card.get("type_line", ""),
                card.get("name", ""),
                card.get("set", ""),
                card.get("released_at", ""),
            ]
            for key, card in sorted(
                self.maximal_types.items(), key=lambda item: get_sort_key(item[1])
            )
        ]


class PromoTypesAggregator(Aggregator):
    def __init__(self, description: str = ""):
        super().__init__("promo_types_by_name", description)
        self.data: Dict[str, Set[str]] = defaultdict(set)
        self.column_names = ["Name", "Promo Types", "Count"]
        self.column_widths = ["16rem", "32rem", "4rem"]

    def process_card(self, card: Dict[str, Any]) -> None:
        name = card.get("name")
        promo_types = card.get("promo_types", [])
        if promo_types:
            self.data[name].update(promo_types)

    def get_sorted_data(self) -> List[List[Any]]:
        return sorted(
            [
                [name, ", ".join(sorted(promo_types)), len(promo_types)]
                for name, promo_types in self.data.items()
            ],
            key=lambda x: x[2],
            reverse=True,
        )


class FirstCardByPowerToughnessAggregator(Aggregator):
    def __init__(self, description: str = ""):
        super().__init__("first_card_by_power_toughness", description)
        self.data: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.column_names = ["Power", "Toughness", "Name", "Set", "Release Date"]
        self.column_widths = ["4rem", "4rem", "16rem", "4rem", "8rem"]

    def process_card(self, card: Dict[str, Any]) -> None:
        power = card.get("power", "")
        toughness = card.get("toughness", "")

        if power == "" or toughness == "":
            return

        key = (power, toughness)

        if key not in self.data or get_sort_key(card) < get_sort_key(self.data[key]):
            self.data[key] = card

    def get_sorted_data(self) -> List[List[Any]]:
        return [
            [
                power,
                toughness,
                card.get("name", ""),
                card.get("set", ""),
                card.get("released_at", ""),
            ]
            for (power, toughness), card in sorted(
                self.data.items(), key=lambda item: get_sort_key(item[1])
            )
        ]
