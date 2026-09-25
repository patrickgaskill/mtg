"""Base aggregator class and shared utilities."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import markdown
from jinja2 import Template


class Aggregator(ABC):
    """Abstract base class for all aggregators."""

    def __init__(
        self,
        name: str,
        display_name: str,
        description: str = "",
        explanation: str = "",
    ):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.explanation = explanation
        self.column_defs = []
        self.warnings: list[str] = []
        self.type_filters: list[dict[str, str]] = []

    @abstractmethod
    def process_card(self, card: dict[str, Any]) -> None:
        """Process a single card."""
        pass

    @abstractmethod
    def get_sorted_data(self) -> list[dict[str, Any]]:
        """Return sorted data for display."""
        pass

    def load_types(self, file_path: Path) -> set[str]:
        """Load one type per line from a text file, recording a warning on failure."""
        try:
            with file_path.resolve().open("r", encoding="utf-8") as f:
                return {line.strip() for line in f if line.strip()}
        except OSError as e:
            self.warnings.append(f"Error: Failed to load types from {file_path}: {e}")
            return set()

    def generate_html_file(
        self,
        output_folder: Path,
        template: Template,
        nav_links: list[dict[str, str]],
        data: list[dict[str, Any]] | None = None,
    ) -> None:
        """Generate HTML and JSON files for this aggregator.

        Pass `data` when it was already computed to avoid sorting it again.
        """
        if data is None:
            data = self.get_sorted_data()

        # Generate JSON file
        json_filename = f"{self.name}.json"
        json_filepath = output_folder / json_filename
        with json_filepath.open("w", encoding="utf-8") as json_file:
            json.dump(data, json_file)

        # Convert markdown explanation to HTML if present
        explanation_html = ""
        if self.explanation:
            explanation_html = markdown.markdown(
                self.explanation, extensions=["fenced_code", "tables"]
            )

        # Generate HTML file using template
        html_content = template.render(
            title=self.display_name,
            display_name=self.display_name,
            description=self.description,
            explanation=explanation_html,
            nav_links=nav_links,
            data_file=json_filename,
            page_url=f"{self.name}.html",
            column_defs=self.column_defs,
            type_filters=self.type_filters,
        )

        output_file = output_folder / f"{self.name}.html"
        with output_file.open("w", encoding="utf-8") as f:
            f.write(html_content)
