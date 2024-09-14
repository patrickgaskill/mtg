from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List

import ijson
import typer
import yaml
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.progress import wrap_file

from file_utils import download_default_cards, find_latest_default_cards


@dataclass
class Counter:
    condition: Callable[[Dict[str, Any]], Any]
    column_names: List[str]
    max_field: str = ""
    count_finishes: bool = True
    data: Dict[Any, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int))
    )


def update_counter(counter: Counter, key: Any, card: Dict[str, Any]) -> None:
    if counter.max_field:
        max_value = card.get(counter.max_field)
        if max_value is not None and max_value.isdigit():
            max_value = int(max_value)
            counter.data[key]["max_value"] = max(
                counter.data[key]["max_value"], max_value
            )
    else:
        if counter.count_finishes:
            finishes = card.get("finishes", [])
            counter.data[key]["count"] += len(finishes)
        else:
            counter.data[key]["count"] += 1


def process_card(counters: Dict[str, Counter], card: Dict[str, Any]) -> None:
    for counter_name, counter in counters.items():
        key = counter.condition(card)
        if key:
            update_counter(counter, key, card)


def generate_html_files(
    counters: Dict[str, Counter], output_folder: Path, template_env: Environment
) -> None:
    template = template_env.get_template("counter_template.html")
    for counter_name, counter in counters.items():
        output_file = output_folder / f"{counter_name}.html"

        sorted_items = sorted(
            counter.data.items(),
            key=lambda x, counter=counter: x[1]["max_value"]
            if counter.max_field
            else x[1]["count"],
            reverse=True,
        )

        html_content = template.render(
            counter_name=counter_name,
            column_names=counter.column_names,
            sorted_items=sorted_items,
            max_field=counter.max_field,
            counters=counters,
        )

        with output_file.open("w") as file:
            file.write(html_content)


def count_cards(
    counters: Dict[str, Counter],
    input_file: Path,
    output_folder: Path,
    template_env: Environment,
) -> None:
    with wrap_file(
        input_file.open("rb"),
        total=input_file.stat().st_size,
        description="Counting cards",
    ) as file:
        for card in ijson.items(file, "item"):
            process_card(counters, card)

    generate_html_files(counters, output_folder, template_env)


app = typer.Typer()


@app.command()
def main(
    download: bool = typer.Option(
        False, help='Download the "default-cards" file from Scryfall.'
    ),
    data_folder: Path = typer.Option(
        Path("data"),
        help='The data folder where the "default-cards" file will be saved.',
    ),
    count: bool = typer.Option(
        False, help="Count cards based on the specified configurations."
    ),
):
    # Set up rich console
    console = Console()

    # Download the "default-cards" file if the --download flag is set
    if download:
        input_file = download_default_cards(data_folder, console)
    else:
        input_file = find_latest_default_cards(data_folder)

    if input_file is None:
        console.print(
            "[red]No 'default-cards' file found. Please download the file using the --download flag.[/red]"
        )
        raise typer.Exit()

    # Set up Jinja template environment
    template_loader = FileSystemLoader(searchpath="./templates")
    template_env = Environment(loader=template_loader)

    # Count cards if the --count flag is set
    if count:
        # Load counter configurations from YAML file
        with open("counter_config.yaml", "r") as file:
            config = yaml.safe_load(file)
            counters = {
                name: Counter(
                    condition=eval(config["condition"]),
                    column_names=config["column_names"],
                    max_field=config.get("max_field", ""),
                    count_finishes=config.get("count_finishes", True),
                )
                for name, config in config["counters"].items()
            }

        # Create output folder with timestamp inside the data folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_folder = data_folder / "output" / timestamp
        output_folder.mkdir(parents=True, exist_ok=True)

        # Count cards and populate counters
        count_cards(counters, input_file, output_folder, template_env)
        console.print(
            "[green]Card counting complete. HTML files generated in the output folder.[/green]"
        )


if __name__ == "__main__":
    app()
