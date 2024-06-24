import logging
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from jinja2 import Template

# Constants
BASIC_LAND_TYPES = {"Forest", "Island", "Mountain", "Plains", "Swamp"}
NON_TRADITIONAL_SET_TYPES = {"memorabilia", "funny"}
NON_TRADITIONAL_LAYOUTS = {"emblem", "token"}
NON_TRADITIONAL_BORDERS = {"silver", "gold"}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Aggregator(ABC):
    @abstractmethod
    def process_card(self, card: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_sorted_data(self) -> List[Tuple[Any, Any]]:
        pass

    def generate_html_file(self, output_folder: Path, template: Template) -> None:
        output_file = output_folder / f"{self.name}.html"

        sorted_data = self.get_sorted_data()

        html_content = template.render(
            name=self.name,
            column_names=self.column_names,
            items=sorted_data,
        )

        try:
            with output_file.open("w", encoding="utf-8") as f:
                f.write(html_content)
        except IOError as e:
            logger.error(f"Failed to write HTML file {output_file}: {e}")


class CountAggregator(Aggregator):
    def __init__(self, name: str, key_fields: List[str], count_finishes: bool = False):
        self.data: Dict[Tuple, int] = defaultdict(int)
        self.name = name
        self.key_fields = key_fields
        self.count_finishes = count_finishes
        self.column_names = key_fields + ["Count"]

    def process_card(self, card: Dict[str, Any]) -> None:
        key = tuple(card.get(field) for field in self.key_fields)
        self.data[key] += len(card.get("finishes", [])) if self.count_finishes else 1

    def get_sorted_data(self) -> List[Tuple[Tuple, int]]:
        return sorted(self.data.items(), key=lambda item: item[1], reverse=True)


class MaxCollectorNumberBySetAggregator(Aggregator):
    def __init__(self):
        self.data: Dict[str, int] = defaultdict(int)
        self.name = "max_collector_number_by_set"
        self.column_names = ["Set", "Max Collector Number"]

    def process_card(self, card: Dict[str, Any]) -> None:
        collector_number = card.get("collector_number")
        if collector_number is not None and collector_number.isdigit():
            key = card.get("set")
            collector_number = int(collector_number)
            self.data[key] = max(self.data[key], collector_number)

    def get_sorted_data(self) -> List[Tuple[str, int]]:
        return sorted(self.data.items(), key=lambda item: item[1], reverse=True)


class CountCardIllustrationsBySetAggregator(Aggregator):
    def __init__(self):
        self.data: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        self.name = "count_card_illustrations_by_set"
        self.column_names = ["Set", "Name", "Count"]

    def process_card(self, card: Dict[str, Any]) -> None:
        key = (card.get("set"), card.get("name"))
        self.data[key].add(card.get("illustration_id"))

    def get_sorted_data(self) -> List[Tuple[Tuple[str, str], int]]:
        return sorted(
            ((key, len(illustrations)) for key, illustrations in self.data.items()),
            key=lambda item: item[1],
            reverse=True,
        )


class MaximalPrintedTypesAggregator(Aggregator):
    def __init__(self, all_creature_types_file: Path, all_land_types_file: Path):
        self.maximal_types: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        self.name = "maximal_printed_types"
        self.column_names = ["Types", "Name", "Set", "Release Date"]
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
            (
                (
                    card.get("type_line", ""),
                    card.get("name", ""),
                    card.get("set", ""),
                ),
                card.get("released_at", ""),
            )
            for key, card in sorted(
                self.maximal_types.items(), key=lambda item: get_sort_key(item[1])
            )
        ]


def extract_types(card: Dict[str, Any]) -> Set[str]:
    text = card.get("type_line", "").replace("Time Lord", "Time-Lord")
    words = re.findall(r"\b\w+\b", text)
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
