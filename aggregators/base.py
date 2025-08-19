"""Base aggregator class and shared utilities."""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Template

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Aggregator(ABC):
    """Abstract base class for all aggregators."""

    def __init__(self, name: str, display_name: str, description: str = ""):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.column_defs = []

    @abstractmethod
    def process_card(self, card: Dict[str, Any]) -> None:
        """Process a single card."""
        pass

    @abstractmethod
    def get_sorted_data(self) -> List[Dict[str, Any]]:
        """Return sorted data for display."""
        pass

    def generate_html_file(
        self, output_folder: Path, template: Template, nav_links: List[Dict[str, str]]
    ) -> None:
        """Generate HTML and JSON files for this aggregator."""
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
