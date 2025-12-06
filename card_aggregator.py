import http.server
import json
import os
import socketserver
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Annotated, Dict, List, Optional

import ijson
import requests
import typer
from jinja2 import Environment, FileSystemLoader
from requests.exceptions import (
    ChunkedEncodingError,
    ConnectionError,
    HTTPError,
    RequestException,
    Timeout,
)
from rich.console import Console
from rich.panel import Panel
from rich.progress import DownloadColumn, Progress, SpinnerColumn, TimeElapsedColumn, wrap_file
from rich.table import Table
from rich.text import Text

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
    help="🎴 MTG Card Data Aggregator - Generate interactive reports from Scryfall data",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

# Global state for verbose/quiet modes
_verbose = False
_quiet = False


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show detailed output")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Minimal output")] = False,
):
    """🎴 MTG Card Aggregator - Process Scryfall data and generate interactive reports"""
    global _verbose, _quiet
    _verbose = verbose
    _quiet = quiet
    if quiet:
        console.quiet = True


def create_all_aggregators() -> List[Aggregator]:
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
        ),
        CountCardIllustrationsBySetAggregator(
            description="Count of unique card illustrations by set"
        ),
        MaxCollectorNumberBySetAggregator(
            description="Maximum collector number by set"
        ),
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
        SupercycleTimeAggregator(
            supercycles_file=MANUAL_DATA_FOLDER / "supercycles.yaml"
        ),
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
    """📊 Show information about downloaded data and available aggregators"""
    # Check for latest download
    latest = find_latest_default_cards(DOWNLOADED_DATA_FOLDER)

    if latest:
        size = latest.stat().st_size / (1024 * 1024)  # MB
        modified = datetime.fromtimestamp(latest.stat().st_mtime)

        data_info = f"""[bold]Latest Data:[/bold] {latest.name}
[bold]Size:[/bold] {size:.1f} MB
[bold]Downloaded:[/bold] {modified.strftime("%Y-%m-%d %H:%M:%S")}
[bold]Path:[/bold] {latest}"""
    else:
        data_info = "[yellow]No data downloaded yet. Run 'download' command.[/yellow]"

    console.print(Panel(data_info, title="📦 Data Status", border_style="blue"))

    # Check for type files
    creature_types_file = DOWNLOADED_DATA_FOLDER / ALL_CREATURE_TYPES_FILE
    land_types_file = DOWNLOADED_DATA_FOLDER / ALL_LAND_TYPES_FILE

    if creature_types_file.exists() and land_types_file.exists():
        creature_modified = datetime.fromtimestamp(creature_types_file.stat().st_mtime)
        land_modified = datetime.fromtimestamp(land_types_file.stat().st_mtime)

        with creature_types_file.open() as f:
            creature_count = sum(1 for _ in f)
        with land_types_file.open() as f:
            land_count = sum(1 for _ in f)

        types_info = f"""[bold]Creature Types:[/bold] {creature_count} types (updated {creature_modified.strftime("%Y-%m-%d")})
[bold]Land Types:[/bold] {land_count} types (updated {land_modified.strftime("%Y-%m-%d")})"""
    else:
        types_info = "[yellow]Type files not found. Run 'update-types' command.[/yellow]"

    console.print(Panel(types_info, title="🏷️  Type Data", border_style="green"))

    # Show aggregator count
    agg_count = len(create_all_aggregators())
    console.print(f"\n[cyan]Available Aggregators:[/cyan] {agg_count} (use '[bold]list[/bold]' command to see details)")


@app.command(name="list")
def list_aggregators():
    """📋 List all available aggregators"""
    table = Table(title="Available Aggregators", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Display Name", style="green")
    table.add_column("Description")

    for agg in create_all_aggregators():
        table.add_row(agg.name, agg.display_name, agg.description)

    console.print(table)
    console.print(f"\n[dim]Total: {len(create_all_aggregators())} aggregators[/dim]")


@app.command()
def update_types():
    """🏷️  Update creature and land types from MTG comprehensive rules"""
    console.print("Fetching the latest comprehensive rules...")
    try:
        creature_types, land_types = fetch_and_parse_types()
    except ValueError as e:
        # fetch_and_parse_types raises ValueError for network and parsing errors
        console.print(f"[red]Error fetching types: {e}[/red]")
        if "Network error" in str(e) or "timeout" in str(e).lower():
            console.print(
                "[yellow]Please check your internet connection and try again.[/yellow]"
            )
        elif "HTTP error" in str(e):
            console.print(
                "[yellow]The Magic rules website may be temporarily unavailable.[/yellow]"
            )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error fetching types: {e}[/red]")
        raise typer.Exit(1)

    # Update creature types file
    creature_types_file = DOWNLOADED_DATA_FOLDER / ALL_CREATURE_TYPES_FILE
    try:
        with creature_types_file.open("w") as f:
            for creature_type in sorted(creature_types):
                f.write(f"{creature_type}\n")
        console.print(
            f"[green]Updated {ALL_CREATURE_TYPES_FILE} with {len(creature_types)} types.[/green]"
        )
    except IOError as e:
        console.print(f"[red]Error writing to {ALL_CREATURE_TYPES_FILE}: {e}[/red]")

    # Update land types file
    land_types_file = DOWNLOADED_DATA_FOLDER / ALL_LAND_TYPES_FILE
    try:
        with land_types_file.open("w") as f:
            for land_type in sorted(land_types):
                f.write(f"{land_type}\n")
        console.print(
            f"[green]Updated {ALL_LAND_TYPES_FILE} with {len(land_types)} types.[/green]"
        )
    except IOError as e:
        console.print(f"[red]Error writing to {ALL_LAND_TYPES_FILE}: {e}[/red]")


@app.command()
def download():
    """📥 Download latest Scryfall bulk data"""
    console.print("Downloading bulk data files from Scryfall...")

    try:
        response = requests.get("https://api.scryfall.com/bulk-data", timeout=30)
        response.raise_for_status()
        bulk_data_files = response.json()["data"]
    except (ConnectionError, Timeout) as e:
        console.print(f"[red]Network error while fetching bulk data list: {e}[/red]")
        console.print(
            "[yellow]Please check your internet connection and try again.[/yellow]"
        )
        raise typer.Exit(1)
    except HTTPError as e:
        console.print(f"[red]HTTP error while fetching bulk data list: {e}[/red]")
        console.print(
            "[yellow]The Scryfall API may be temporarily unavailable.[/yellow]"
        )
        raise typer.Exit(1)
    except RequestException as e:
        console.print(f"[red]Request error while fetching bulk data list: {e}[/red]")
        raise typer.Exit(1)
    except (KeyError, json.JSONDecodeError) as e:
        console.print(f"[red]Error parsing bulk data response: {e}[/red]")
        console.print(
            "[yellow]The Scryfall API response format may have changed.[/yellow]"
        )
        raise typer.Exit(1)

    try:
        default_cards_file = next(
            file for file in bulk_data_files if file["type"] == "default_cards"
        )
    except StopIteration:
        console.print("[red]Could not find default_cards file in bulk data list[/red]")
        raise typer.Exit(1)

    download_url = default_cards_file["download_uri"]
    file_name = Path(download_url).name
    DOWNLOADED_DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    file_path = DOWNLOADED_DATA_FOLDER / file_name

    try:
        response = requests.get(download_url, stream=True, timeout=30)
        response.raise_for_status()
    except (ConnectionError, Timeout) as e:
        console.print(f"[red]Network error while downloading file: {e}[/red]")
        console.print(
            "[yellow]Please check your internet connection and try again.[/yellow]"
        )
        raise typer.Exit(1)
    except HTTPError as e:
        console.print(f"[red]HTTP error while downloading file: {e}[/red]")
        console.print(
            "[yellow]The download URL may be invalid or the file may be temporarily unavailable.[/yellow]"
        )
        raise typer.Exit(1)
    except RequestException as e:
        console.print(f"[red]Request error while downloading file: {e}[/red]")
        raise typer.Exit(1)

    try:
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
    except ChunkedEncodingError as e:
        console.print(f"[red]Connection lost during download: {e}[/red]")
        console.print(
            "[yellow]The download was interrupted. Please try again.[/yellow]"
        )
        # Clean up partially downloaded file
        if file_path.exists():
            file_path.unlink()
        raise typer.Exit(1)
    except (ConnectionError, Timeout) as e:
        console.print(f"[red]Network error during download: {e}[/red]")
        console.print(
            "[yellow]The connection was lost during download. Please try again.[/yellow]"
        )
        # Clean up partially downloaded file
        if file_path.exists():
            file_path.unlink()
        raise typer.Exit(1)
    except IOError as e:
        console.print(f"[red]Error writing file to disk: {e}[/red]")
        console.print("[yellow]Please check disk space and write permissions.[/yellow]")
        # Clean up partially downloaded file
        if file_path.exists():
            file_path.unlink()
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error during download: {e}[/red]")
        # Clean up partially downloaded file
        if file_path.exists():
            file_path.unlink()
        raise typer.Exit(1)

    console.print(
        f"[green]Download complete:[/green] [bold]{file_path}[/bold]", highlight=False
    )
    return file_path


@app.command()
def all(
    serve: Annotated[bool, typer.Option(help="Start server after processing")] = True,
    skip_download: Annotated[bool, typer.Option(help="Skip downloading fresh data")] = False,
    skip_types: Annotated[bool, typer.Option(help="Skip updating creature/land types")] = False,
):
    """🚀 Run complete workflow: download → update-types → process → serve"""
    console.print(Panel.fit(
        "🎴 MTG Card Aggregator - Complete Workflow",
        border_style="bold blue"
    ))

    steps_total = 4 - (1 if skip_download else 0) - (1 if skip_types else 0)
    current_step = 1

    if not skip_download:
        console.print(f"\n[bold blue]Step {current_step}/{steps_total}:[/bold blue] Downloading data...")
        download()
        current_step += 1

    if not skip_types:
        console.print(f"\n[bold blue]Step {current_step}/{steps_total}:[/bold blue] Updating types...")
        update_types()
        current_step += 1

    console.print(f"\n[bold blue]Step {current_step}/{steps_total}:[/bold blue] Processing cards...")

    # Find the latest input file
    input_file = find_latest_default_cards(DOWNLOADED_DATA_FOLDER)
    if input_file is None:
        console.print("[red]No data file found. Please run with download enabled.[/red]")
        raise typer.Exit(1)

    # Create timestamped output folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = OUTPUT_DATA_FOLDER / timestamp

    # Call run_internal with serve option
    run_internal(
        input_file=input_file,
        output_folder=output_folder,
        serve=serve,
        only=None,
        exclude=None,
        dry_run=False,
    )

    console.print(f"\n[bold green]✓ Workflow complete![/bold green]")


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


def generate_nav_links(aggregators: List[Aggregator]) -> List[Dict[str, str]]:
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
            "description": agg.description,  # Include description here
        }
        for agg in aggregators
    ]


def run_internal(
    input_file: Path,
    output_folder: Path,
    serve: bool,
    only: Optional[List[str]],
    exclude: Optional[List[str]],
    dry_run: bool,
) -> None:
    """Internal function that does the actual processing work."""
    # Use the provided input_file if specified, otherwise find the latest
    if input_file is None:
        input_file = find_latest_default_cards(DOWNLOADED_DATA_FOLDER)
        if input_file is None:
            console.print(
                "[red]No 'default-cards' file found. Please download the file using the download command.[/red]"
            )
            raise typer.Exit()

    # Use the provided output_folder if specified, otherwise create a timestamped folder
    if output_folder is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_folder = OUTPUT_DATA_FOLDER / timestamp

    # Ensure the output folder exists
    if not dry_run:
        output_folder.mkdir(parents=True, exist_ok=True)

    # Show header
    console.print(Panel.fit(
        "🎴 MTG Card Aggregator",
        subtitle="Processing Scryfall data",
        border_style="blue"
    ))
    console.print(f"📥 Input:  [cyan]{input_file.name}[/cyan]")
    console.print(f"📤 Output: [cyan]{output_folder.name if output_folder else 'N/A (dry run)'}[/cyan]")

    # Create all aggregators
    all_aggregators = create_all_aggregators()

    # Filter aggregators based on only/exclude options
    if only:
        aggregators = [a for a in all_aggregators if a.name in only]
        if not aggregators:
            console.print(f"[yellow]Warning: No aggregators match --only filter. Available: {[a.name for a in all_aggregators]}[/yellow]")
            return
    elif exclude:
        aggregators = [a for a in all_aggregators if a.name not in exclude]
        if not aggregators:
            console.print("[yellow]Warning: All aggregators excluded by --exclude filter[/yellow]")
            return
    else:
        aggregators = all_aggregators

    if dry_run:
        console.print(f"\n[yellow]DRY RUN - No files will be generated[/yellow]\n")
        table = Table(title="Aggregators to Process", show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Name", style="cyan")
        table.add_column("Display Name", style="green")

        for idx, agg in enumerate(aggregators, 1):
            table.add_row(str(idx), agg.name, agg.display_name)

        console.print(table)
        console.print(f"\n[dim]Total: {len(aggregators)} aggregators would be processed[/dim]")
        return

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
    template_env.globals.update(zip=zip)
    base_template = template_env.get_template("base_template.html")
    index_template = template_env.get_template("index_template.html")

    # Generate index.html
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
            console.print(
                f"[red]Error generating files for {aggregator.name}: {e}[/red]"
            )

        # Save sorted data from each aggregator to a JSON file
        try:
            json_filename = f"{aggregator.name.lower().replace(' ', '_')}.json"
            json_filepath = output_folder / json_filename
            with json_filepath.open("w", encoding="utf-8") as json_file:
                json.dump(aggregator.get_sorted_data(), json_file)
        except Exception as e:
            console.print(
                f"[red]Error saving JSON data for {aggregator.name}: {e}[/red]"
            )

    # Show summary table
    console.print()
    table = Table(title="Processing Summary", show_header=True, header_style="bold green")
    table.add_column("Aggregator", style="cyan")
    table.add_column("Records", justify="right", style="green")

    for agg in aggregators:
        data = agg.get_sorted_data()
        table.add_row(agg.display_name, str(len(data)))

    console.print(table)

    console.print(f"\n[bold green]✓ Processing complete![/bold green]")
    console.print(f"[green]Output:[/green] {output_folder.resolve()}")

    # Start HTTP server if requested
    if serve:
        serve_and_open_browser(output_folder)


@app.command()
def run(
    input_file: Annotated[Optional[Path], typer.Option(
        help="Path to Scryfall JSON file (auto-detects latest if not specified)"
    )] = None,
    output_folder: Annotated[Optional[Path], typer.Option(
        "--output", "-o",
        help="Output directory (default: timestamped folder in data/output/)"
    )] = None,
    serve: Annotated[bool, typer.Option(
        "--serve", "-s",
        help="🌐 Start HTTP server and open browser after generation"
    )] = False,
    only: Annotated[Optional[List[str]], typer.Option(
        help="Only run specific aggregators (can specify multiple times)"
    )] = None,
    exclude: Annotated[Optional[List[str]], typer.Option(
        help="Exclude specific aggregators (can specify multiple times)"
    )] = None,
    dry_run: Annotated[bool, typer.Option(
        "--dry-run",
        help="Show what would be generated without processing"
    )] = False,
):
    """⚙️  Generate reports from card data"""
    # Use the provided input_file if specified, otherwise find the latest
    if input_file is None:
        input_file = find_latest_default_cards(DOWNLOADED_DATA_FOLDER)
        if input_file is None:
            console.print(
                "[red]No 'default-cards' file found. Please download the file using the download command.[/red]"
            )
            raise typer.Exit()

    # Use the provided output_folder if specified, otherwise create a timestamped folder
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

    # Change to the output directory
    os.chdir(directory.resolve())

    # Create server
    httpd = socketserver.TCPServer(("", port), handler)

    url = f"http://localhost:{port}/index.html"

    console.print()
    console.print(Panel(
        f"[green]✓[/green] Server running at [link={url}]{url}[/link]\n"
        f"[yellow]Press Ctrl+C to stop[/yellow]",
        title="🌐 HTTP Server",
        border_style="green"
    ))

    # Open browser in a separate thread
    threading.Timer(
        1.0, lambda: webbrowser.open(url)
    ).start()

    try:
        # Start server
        httpd.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    app()
