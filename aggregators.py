from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict

from jinja2 import Template

type Card = Dict[str, Any]


class Aggregator(ABC):
    @abstractmethod
    def process_card(self, card: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_sorted_data(self):
        pass

    def generate_html_file(self, output_folder: Path, template: Template) -> None:
        output_file = output_folder / f"{self.name}.html"

        sorted_data = self.get_sorted_data()

        html_content = template.render(
            name=self.name,
            column_names=self.column_names,
            items=sorted_data,
        )

        with output_file.open("w", encoding="utf-8") as f:
            f.write(html_content)


class CountAggregator(Aggregator):
    def __init__(self, name: str, key_fields: list[str], count_finishes=False):
        self.data: Dict[tuple, int] = defaultdict(int)
        self.name = name
        self.key_fields = key_fields
        self.count_finishes = count_finishes
        self.column_names = key_fields + ["Count"]

    def process_card(self, card: Dict[str, Any]) -> None:
        key = tuple(card.get(field) for field in self.key_fields)
        self.data[key] += len(card.get("finishes", [])) if self.count_finishes else 1

    def get_sorted_data(self):
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

    def get_sorted_data(self):
        return sorted(self.data.items(), key=lambda item: item[1], reverse=True)
