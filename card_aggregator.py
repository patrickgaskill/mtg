import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import ijson
import requests
import typer
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.progress import DownloadColumn, Progress, wrap_file

from aggregators import (
    CountAggregator,
    CountCardIllustrationsBySetAggregator,
    MaxCollectorNumberBySetAggregator,
    MaximalPrintedTypesAggregator,
)

DATA_FOLDER = Path("data").resolve()
ALL_CREATURE_TYPES_FILE = "all_creature_types.txt"
ALL_LAND_TYPES_FILE = "all_land_types.txt"

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def download():
    console.print("Downloading bulk data files from Scryfall...")
    response = requests.get("https://api.scryfall.com/bulk-data")
    bulk_data_files = response.json()["data"]

    default_cards_file = next(
        file for file in bulk_data_files if file["type"] == "default_cards"
    )
    download_url = default_cards_file["download_uri"]
    file_name = Path(download_url).name
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    file_path = DATA_FOLDER / file_name

    response = requests.get(download_url, stream=True)

    with Progress(*Progress.get_default_columns(), DownloadColumn()) as progress:
        task = progress.add_task(
            f"Downloading {default_cards_file['name']}",
            filename=default_cards_file["name"],
            total=int(default_cards_file["size"]),
        )

        with file_path.open("wb") as file:
            for data in response.iter_content(chunk_size=1024):
                size = file.write(data)
                progress.update(task, advance=size)

    console.print(
        f"[green]Download complete:[/green] [bold]{file_path}[/bold]", highlight=False
    )
    return file_path


def find_latest_default_cards(data_folder: Path) -> Optional[Path]:
    """
    Find the latest "default-cards" file in the specified data folder.

    Args:
        data_folder (Path): The path to the data folder.

    Returns:
        Optional[Path]: The path to the latest "default-cards" file, or None if not found.
    """
    default_cards_files = list(data_folder.glob("default-cards-*.json"))
    return (
        max(default_cards_files, key=lambda f: f.stem.split("-")[-1])
        if default_cards_files
        else None
    )


@app.command()
def run():
    input_file = find_latest_default_cards(DATA_FOLDER)

    if input_file is None:
        console.print(
            "[red]No 'default-cards' file found. Please download the file using the download command.[/red]"
        )
        raise typer.Exit()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = DATA_FOLDER / "output" / timestamp
    output_folder.mkdir(parents=True, exist_ok=True)

    aggregators = [
        CountAggregator(name="cards_by_name", key_fields=["name"]),
        CountAggregator(
            name="finishes_by_name", key_fields=["name"], count_finishes=True
        ),
        CountAggregator(name="cards_by_set_name", key_fields=["set", "name"]),
        CountAggregator(
            name="finishes_by_set_name",
            key_fields=["set", "name"],
            count_finishes=True,
        ),
        CountCardIllustrationsBySetAggregator(),
        MaxCollectorNumberBySetAggregator(),
        MaximalPrintedTypesAggregator(
            all_creature_types_file=DATA_FOLDER / ALL_CREATURE_TYPES_FILE,
            all_land_types_file=DATA_FOLDER / ALL_LAND_TYPES_FILE,
        ),
    ]

    with wrap_file(
        input_file.open("rb"),
        total=input_file.stat().st_size,
        description="Processing cards",
    ) as file:
        for card in ijson.items(file, "item"):
            for aggregator in aggregators:
                try:
                    aggregator.process_card(card)
                except Exception as e:
                    console.print(
                        f"[red]Error processing card {card.get('name', 'Unknown')}: {e}[/red]"
                    )

    template_env = Environment(loader=FileSystemLoader(searchpath="./templates"))
    template = template_env.get_template("counter_template.html")

    for aggregator in aggregators:
        try:
            aggregator.generate_html_file(output_folder, template)
        except Exception as e:
            console.print(
                f"[red]Error generating HTML for {aggregator.name}: {e}[/red]"
            )

    console.print(
        f"[green]Card processing complete. HTML files generated in {output_folder}.[/green]"
    )


if __name__ == "__main__":
    app()
