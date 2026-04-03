import http.server
import json
import os
import socketserver
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Annotated

import ijson
import requests
import typer
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from requests.exceptions import (
    ChunkedEncodingError,
    ConnectionError,
    HTTPError,
    RequestException,
    Timeout,
)

from aggregators import (
    Aggregator,
    CountAggregator,
    CountCardIllustrationsBySetAggregator,
    FirstCardByGeneralizedManaCostAggregator,
    FirstCardByPowerToughnessAggregator,
    FoilTypesAggregator,
    MaxCollectorNumberBySetAggregator,
    MaximalPrintedTypesAggregator,
    MaximalTypesWithEffectsAggregator,
    PromoTypesAggregator,
    SupercycleTimeAggregator,
)
from type_updater import fetch_and_parse_types

DATA_FOLDER = Path("data").resolve()
DOWNLOADED_DATA_FOLDER = DATA_FOLDER / "downloads"
MANUAL_DATA_FOLDER = DATA_FOLDER / "manual"
OUTPUT_DATA_FOLDER = DATA_FOLDER / "output"
ALL_CREATURE_TYPES_FILE = "all_creature_types.txt"
ALL_LAND_TYPES_FILE = "all_land_types.txt"
DEFAULT_INPUT_FILE = DOWNLOADED_DATA_FOLDER / "default-cards.json"
DEFAULT_OUTPUT_FOLDER = OUTPUT_DATA_FOLDER

app = typer.Typer(
    name="mtg-aggregator",
    help="MTG Card Data Aggregator - Generate interactive reports from Scryfall data",
    no_args_is_help=True,
)


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show detailed output")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Minimal output")] = False,
):
    """MTG Card Aggregator - Process Scryfall data and generate interactive reports"""
    if quiet:
        logger.disable("__main__")
    elif verbose:
        logger.enable("__main__")


def create_all_aggregators() -> list[Aggregator]:
    """Create and return all available aggregators."""
    return [
        CountAggregator(
            name="count_cards_by_name",
            display_name="Cards by Name",
            key_fields=["name"],
            description="Count of unique cards by name",
        ),
        CountAggregator(
            name="count_finishes_by_name",
            display_name="Card Finishes by Name",
            key_fields=["name"],
            count_finishes=True,
            description="Count of card finishes by name",
            explanation="""
## What are Card Finishes?

A **finish** refers to the physical treatment applied to a Magic card. Each printing of a card
can be available in different finishes, and Scryfall tracks which finishes are available for
each printing.

**Types of finishes:**
- **Nonfoil** - Standard non-reflective card stock (the traditional finish)
- **Foil** - Premium reflective treatment with a shiny surface
- **Etched** - Textured finish available on select printings

## About This Report

This report counts the total number of **finish variations** available for each unique card name
across all printings. For example, if a card was printed in three different sets, and each
printing is available in both foil and nonfoil, that card would have a count of 6 finish variations.

**Note:** Each card object in Scryfall represents a specific printing, not the abstract card
concept.
The same card name printed in different sets or with different finishes appears as separate card
objects in the data.
            """,
        ),
        CountAggregator(
            name="count_cards_by_set_name",
            display_name="Cards by Set and Name",
            key_fields=["set", "name"],
            description="Count of cards by set and name",
        ),
        CountAggregator(
            name="count_finishes_by_set_name",
            display_name="Card Finishes by Set and Name",
            key_fields=["set", "name"],
            count_finishes=True,
            description="Count of card finishes by set and name",
            explanation="""
## What are Card Finishes?

A **finish** refers to the physical treatment applied to a Magic card. The available finish
types are:

- **Nonfoil** - Standard non-reflective card stock
- **Foil** - Premium reflective treatment
- **Etched** - Textured finish available on select printings

## About This Report

This report shows how many finish variations exist for each card within each specific set.
For example, if "Lightning Bolt" in Alpha is available in nonfoil only, it would show a
count of 1. If "Lightning Bolt" in a modern set is available in both foil and nonfoil,
it would show a count of 2.

This helps identify which printings have multiple finish options available.
            """,
        ),
        CountCardIllustrationsBySetAggregator(
            description="Count of unique card illustrations by set"
        ),
        MaxCollectorNumberBySetAggregator(description="Maximum collector number by set"),
        MaximalPrintedTypesAggregator(
            all_creature_types_file=DOWNLOADED_DATA_FOLDER / ALL_CREATURE_TYPES_FILE,
            all_land_types_file=DOWNLOADED_DATA_FOLDER / ALL_LAND_TYPES_FILE,
            description="Cards with maximal printed types",
        ),
        PromoTypesAggregator(description="Promo types by card name"),
        FirstCardByPowerToughnessAggregator(
            description="First card for each unique power/toughness combination"
        ),
        FoilTypesAggregator(description="Foil types by card name"),
        SupercycleTimeAggregator(supercycles_file=MANUAL_DATA_FOLDER / "supercycles.yaml"),
        MaximalTypesWithEffectsAggregator(
            all_creature_types_file=DOWNLOADED_DATA_FOLDER / ALL_CREATURE_TYPES_FILE,
            all_land_types_file=DOWNLOADED_DATA_FOLDER / ALL_LAND_TYPES_FILE,
            description="Cards with maximal types, considering global effects",
        ),
        FirstCardByGeneralizedManaCostAggregator(
            description="First card for each generalized mana cost"
        ),
    ]


@app.command()
def status():
    """Show information about downloaded data and available aggregators"""
    latest = find_latest_default_cards(DOWNLOADED_DATA_FOLDER)

    if latest:
        size = latest.stat().st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(latest.stat().st_mtime)
        logger.info(
            "Latest data: {} ({:.1f} MB, downloaded {})",
            latest.name,
            size,
            modified.strftime("%Y-%m-%d %H:%M:%S"),
        )
    else:
        logger.warning("No data downloaded yet. Run 'download' command.")

    creature_types_file = DOWNLOADED_DATA_FOLDER / ALL_CREATURE_TYPES_FILE
    land_types_file = DOWNLOADED_DATA_FOLDER / ALL_LAND_TYPES_FILE

    if creature_types_file.exists() and land_types_file.exists():
        creature_modified = datetime.fromtimestamp(creature_types_file.stat().st_mtime)
        land_modified = datetime.fromtimestamp(land_types_file.stat().st_mtime)

        with creature_types_file.open() as f:
            creature_count = sum(1 for _ in f)
        with land_types_file.open() as f:
            land_count = sum(1 for _ in f)

        logger.info(
            "Creature types: {} (updated {})",
            creature_count,
            creature_modified.strftime("%Y-%m-%d"),
        )
        logger.info("Land types: {} (updated {})", land_count, land_modified.strftime("%Y-%m-%d"))
    else:
        logger.warning("Type files not found. Run 'update-types' command.")

    agg_count = len(create_all_aggregators())
    logger.info("Available aggregators: {} (use 'list' command to see details)", agg_count)


@app.command(name="list")
def list_aggregators():
    """List all available aggregators"""
    for agg in create_all_aggregators():
        logger.info("{}: {} - {}", agg.name, agg.display_name, agg.description)
    logger.info("Total: {} aggregators", len(create_all_aggregators()))


@app.command()
def update_types():
    """Update creature and land types from MTG comprehensive rules"""
    logger.info("Fetching the latest comprehensive rules...")
    try:
        creature_types, land_types = fetch_and_parse_types()
    except ValueError as e:
        logger.error("Error fetching types: {}", e)
        if "Network error" in str(e) or "timeout" in str(e).lower():
            logger.warning("Please check your internet connection and try again.")
        elif "HTTP error" in str(e):
            logger.warning("The Magic rules website may be temporarily unavailable.")
        raise typer.Exit(1) from None
    except Exception as e:
        logger.error("Unexpected error fetching types: {}", e)
        raise typer.Exit(1) from None

    creature_types_file = DOWNLOADED_DATA_FOLDER / ALL_CREATURE_TYPES_FILE
    try:
        with creature_types_file.open("w") as f:
            for creature_type in sorted(creature_types):
                f.write(f"{creature_type}\n")
        logger.info("Updated {} with {} types.", ALL_CREATURE_TYPES_FILE, len(creature_types))
    except OSError as e:
        logger.error("Error writing to {}: {}", ALL_CREATURE_TYPES_FILE, e)

    land_types_file = DOWNLOADED_DATA_FOLDER / ALL_LAND_TYPES_FILE
    try:
        with land_types_file.open("w") as f:
            for land_type in sorted(land_types):
                f.write(f"{land_type}\n")
        logger.info("Updated {} with {} types.", ALL_LAND_TYPES_FILE, len(land_types))
    except OSError as e:
        logger.error("Error writing to {}: {}", ALL_LAND_TYPES_FILE, e)


@app.command()
def download():
    """Download latest Scryfall bulk data"""
    logger.info("Downloading bulk data files from Scryfall...")

    try:
        response = requests.get("https://api.scryfall.com/bulk-data", timeout=30)
        response.raise_for_status()
        bulk_data_files = response.json()["data"]
    except (ConnectionError, Timeout) as e:
        logger.error("Network error while fetching bulk data list: {}", e)
        logger.warning("Please check your internet connection and try again.")
        raise typer.Exit(1) from None
    except HTTPError as e:
        logger.error("HTTP error while fetching bulk data list: {}", e)
        logger.warning("The Scryfall API may be temporarily unavailable.")
        raise typer.Exit(1) from None
    except RequestException as e:
        logger.error("Request error while fetching bulk data list: {}", e)
        raise typer.Exit(1) from None
    except (KeyError, json.JSONDecodeError) as e:
        logger.error("Error parsing bulk data response: {}", e)
        logger.warning("The Scryfall API response format may have changed.")
        raise typer.Exit(1) from None

    try:
        default_cards_file = next(
            file for file in bulk_data_files if file["type"] == "default_cards"
        )
    except StopIteration:
        logger.error("Could not find default_cards file in bulk data list")
        raise typer.Exit(1) from None

    download_url = default_cards_file["download_uri"]
    file_name = Path(download_url).name
    DOWNLOADED_DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    file_path = DOWNLOADED_DATA_FOLDER / file_name

    try:
        response = requests.get(download_url, stream=True, timeout=30)
        response.raise_for_status()
    except (ConnectionError, Timeout) as e:
        logger.error("Network error while downloading file: {}", e)
        logger.warning("Please check your internet connection and try again.")
        raise typer.Exit(1) from None
    except HTTPError as e:
        logger.error("HTTP error while downloading file: {}", e)
        logger.warning(
            "The download URL may be invalid or the file may be temporarily unavailable."
        )
        raise typer.Exit(1) from None
    except RequestException as e:
        logger.error("Request error while downloading file: {}", e)
        raise typer.Exit(1) from None

    total_size = int(default_cards_file["size"])
    logger.info(
        "Downloading {} ({:.1f} MB)...",
        default_cards_file["name"],
        total_size / (1024 * 1024),
    )

    try:
        downloaded = 0
        with file_path.open("wb") as file:
            for data in response.iter_content(chunk_size=1024):
                size = file.write(data)
                downloaded += size
    except ChunkedEncodingError as e:
        logger.error("Connection lost during download: {}", e)
        logger.warning("The download was interrupted. Please try again.")
        if file_path.exists():
            file_path.unlink()
        raise typer.Exit(1) from None
    except (ConnectionError, Timeout) as e:
        logger.error("Network error during download: {}", e)
        logger.warning("The connection was lost during download. Please try again.")
        if file_path.exists():
            file_path.unlink()
        raise typer.Exit(1) from None
    except OSError as e:
        logger.error("Error writing file to disk: {}", e)
        logger.warning("Please check disk space and write permissions.")
        if file_path.exists():
            file_path.unlink()
        raise typer.Exit(1) from None
    except Exception as e:
        logger.error("Unexpected error during download: {}", e)
        if file_path.exists():
            file_path.unlink()
        raise typer.Exit(1) from None

    logger.info("Download complete: {}", file_path)
    return file_path


@app.command()
def all(
    serve: Annotated[bool, typer.Option(help="Start server after processing")] = True,
    skip_download: Annotated[bool, typer.Option(help="Skip downloading fresh data")] = False,
    skip_types: Annotated[bool, typer.Option(help="Skip updating creature/land types")] = False,
):
    """Run complete workflow: download, update-types, process, serve"""
    logger.info("Starting MTG Card Aggregator workflow")

    steps_total = 4 - (1 if skip_download else 0) - (1 if skip_types else 0)
    current_step = 1

    if not skip_download:
        logger.info("Step {}/{}: Downloading data...", current_step, steps_total)
        download()
        current_step += 1

    if not skip_types:
        logger.info("Step {}/{}: Updating types...", current_step, steps_total)
        update_types()
        current_step += 1

    logger.info("Step {}/{}: Processing cards...", current_step, steps_total)

    input_file = find_latest_default_cards(DOWNLOADED_DATA_FOLDER)
    if input_file is None:
        logger.error("No data file found. Please run with download enabled.")
        raise typer.Exit(1) from None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = OUTPUT_DATA_FOLDER / timestamp

    run_internal(
        input_file=input_file,
        output_folder=output_folder,
        serve=serve,
        only=None,
        exclude=None,
        dry_run=False,
    )

    logger.info("Workflow complete!")


def find_latest_default_cards(data_folder: Path) -> Path | None:
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


def generate_nav_links(aggregators: list[Aggregator]) -> list[dict[str, str]]:
    """
    Generate navigation links for aggregator HTML pages.

    Args:
        aggregators: List of aggregator instances.

    Returns:
        List of dictionaries containing url, name, display_name, and description.
    """
    return [
        {
            "url": f"{agg.name}.html",
            "name": agg.name,
            "display_name": agg.display_name,
            "description": agg.description,
        }
        for agg in aggregators
    ]


def run_internal(
    input_file: Path,
    output_folder: Path,
    serve: bool,
    only: list[str] | None,
    exclude: list[str] | None,
    dry_run: bool,
) -> None:
    """Internal function that does the actual processing work."""
    if input_file is None:
        input_file = find_latest_default_cards(DOWNLOADED_DATA_FOLDER)
        if input_file is None:
            logger.error("No 'default-cards' file found. Please run the download command.")
            raise typer.Exit()

    if output_folder is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_folder = OUTPUT_DATA_FOLDER / timestamp

    if not dry_run:
        output_folder.mkdir(parents=True, exist_ok=True)

    logger.info("Input: {}", input_file.name)
    logger.info("Output: {}", output_folder.name if output_folder else "N/A (dry run)")

    all_aggregators = create_all_aggregators()

    if only:
        aggregators = [a for a in all_aggregators if a.name in only]
        if not aggregators:
            logger.warning(
                "No aggregators match --only filter. Available: {}",
                [a.name for a in all_aggregators],
            )
            return
    elif exclude:
        aggregators = [a for a in all_aggregators if a.name not in exclude]
        if not aggregators:
            logger.warning("All aggregators excluded by --exclude filter")
            return
    else:
        aggregators = all_aggregators

    if dry_run:
        logger.info("DRY RUN - No files will be generated")
        for idx, agg in enumerate(aggregators, 1):
            logger.info("  {}. {} ({})", idx, agg.display_name, agg.name)
        logger.info("Total: {} aggregators would be processed", len(aggregators))
        return

    logger.info("Processing cards through {} aggregators...", len(aggregators))
    with input_file.open("rb") as file:
        for card in ijson.items(file, "item"):
            for aggregator in aggregators:
                try:
                    aggregator.process_card(card)
                except Exception as e:
                    logger.error("Error processing card {}: {}", card.get("name", "Unknown"), e)

    template_env = Environment(loader=FileSystemLoader(searchpath="./templates"))
    template_env.globals.update(zip=zip)
    base_template = template_env.get_template("base_template.html")
    index_template = template_env.get_template("index_template.html")

    nav_links = generate_nav_links(aggregators)
    index_html = index_template.render(
        nav_links=nav_links,
        generation_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    with (output_folder / "index.html").open("w", encoding="utf-8") as f:
        f.write(index_html)

    for aggregator in aggregators:
        try:
            aggregator.generate_html_file(output_folder, base_template, nav_links)
        except Exception as e:
            logger.error("Error generating files for {}: {}", aggregator.name, e)

        try:
            json_filename = f"{aggregator.name.lower().replace(' ', '_')}.json"
            json_filepath = output_folder / json_filename
            with json_filepath.open("w", encoding="utf-8") as json_file:
                json.dump(aggregator.get_sorted_data(), json_file)
        except Exception as e:
            logger.error("Error saving JSON data for {}: {}", aggregator.name, e)

    # Log summary
    for agg in aggregators:
        data = agg.get_sorted_data()
        logger.info("{}: {} records", agg.display_name, len(data))

    # Log warnings from aggregators (deduplicated)
    seen_warnings = set()
    for agg in aggregators:
        for warning in agg.warnings:
            warning_text = f"[{agg.display_name}] {warning}"
            if warning_text not in seen_warnings:
                seen_warnings.add(warning_text)
                logger.warning(warning_text)

    logger.info("Processing complete!")
    logger.info("Output: {}", output_folder.resolve())

    if serve:
        serve_and_open_browser(output_folder)


@app.command()
def run(
    input_file: Annotated[
        Path | None,
        typer.Option(help="Path to Scryfall JSON file (auto-detects latest if not specified)"),
    ] = None,
    output_folder: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output directory (default: timestamped folder in data/output/)",
        ),
    ] = None,
    serve: Annotated[
        bool,
        typer.Option(
            "--serve",
            "-s",
            help="Start HTTP server and open browser after generation",
        ),
    ] = False,
    only: Annotated[
        list[str] | None,
        typer.Option(help="Only run specific aggregators (can specify multiple times)"),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(help="Exclude specific aggregators (can specify multiple times)"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be generated without processing"),
    ] = False,
):
    """Generate reports from card data"""
    if input_file is None:
        input_file = find_latest_default_cards(DOWNLOADED_DATA_FOLDER)
        if input_file is None:
            logger.error("No 'default-cards' file found. Please run the download command.")
            raise typer.Exit()

    if output_folder is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_folder = OUTPUT_DATA_FOLDER / timestamp

    run_internal(
        input_file=input_file,
        output_folder=output_folder,
        serve=serve,
        only=only,
        exclude=exclude,
        dry_run=dry_run,
    )


def serve_and_open_browser(directory: Path):
    """Start an HTTP server in the given directory and open the browser."""
    port = 8000
    handler = http.server.SimpleHTTPRequestHandler

    os.chdir(directory.resolve())

    httpd = socketserver.TCPServer(("", port), handler)

    url = f"http://localhost:{port}/index.html"

    logger.info("Server running at {}", url)
    logger.info("Press Ctrl+C to stop")

    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    app()
