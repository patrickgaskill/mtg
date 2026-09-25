"""Command-line interface: `mtg <command>` (or `python -m mtg <command>`)."""

import http.server
import socketserver
import sys
import threading
import webbrowser
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

from mtg import scryfall
from mtg.aggregators import AGGREGATOR_CLASSES, AggregatorContext, create_aggregators
from mtg.config import Paths
from mtg.pipeline import TooManyErrors, build_reports, load_type_lists, process_cards
from mtg.rules import fetch_and_parse_types
from mtg.site import write_site

app = typer.Typer(
    name="mtg",
    help="MTG Card Data Aggregator - Generate interactive reports from Scryfall data",
    no_args_is_help=True,
)


class _State:
    """Options set by the top-level callback, shared with every command."""

    paths = Paths()


def get_paths() -> Paths:
    return _State.paths


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show debug output")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Only show warnings")] = False,
    data_dir: Annotated[
        Path, typer.Option("--data-dir", help="Folder for downloaded and generated data")
    ] = Path("data"),
):
    """MTG Card Aggregator - Process Scryfall data and generate interactive reports"""
    _State.paths = Paths(data_dir)
    level = "WARNING" if quiet else "DEBUG" if verbose else "INFO"
    logger.remove()
    logger.add(sys.stderr, level=level)


@app.command()
def status():
    """Show information about downloaded data and available aggregators"""
    paths = get_paths()
    latest = scryfall.find_latest_default_cards(paths.downloads)

    if latest:
        stat = latest.stat()
        logger.info(
            "Latest data: {} ({:.1f} MB, downloaded {})",
            latest.name,
            stat.st_size / (1024 * 1024),
            datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        )
    else:
        logger.warning("No data downloaded yet. Run 'download' command.")

    if paths.types_file.exists():
        type_lists = load_type_lists(paths.types_file)
        modified = datetime.fromtimestamp(paths.types_file.stat().st_mtime)
        logger.info(
            "Type lists: {} creature, {} land (updated {})",
            len(type_lists.creature),
            len(type_lists.land),
            modified.strftime("%Y-%m-%d"),
        )
    else:
        logger.warning("Type lists not found. Run 'update-types' command.")

    logger.info(
        "Available aggregators: {} (use 'list' command to see details)", len(AGGREGATOR_CLASSES)
    )


@app.command(name="list")
def list_aggregators():
    """List all available aggregators"""
    for cls in AGGREGATOR_CLASSES:
        logger.info("{}: {} - {}", cls.name, cls.display_name, cls.description)
    logger.info("Total: {} aggregators", len(AGGREGATOR_CLASSES))


@app.command()
def update_types():
    """Update type lists from the MTG comprehensive rules"""
    logger.info("Fetching the latest comprehensive rules...")
    try:
        type_lists = fetch_and_parse_types()
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

    types_file = get_paths().types_file
    try:
        type_lists.save(types_file)
    except OSError as e:
        logger.error("Error writing to {}: {}", types_file, e)
        raise typer.Exit(1) from None
    logger.info(
        "Updated {}: {} creature, {} land, {} artifact, {} enchantment, {} spell types.",
        types_file,
        len(type_lists.creature),
        len(type_lists.land),
        len(type_lists.artifact),
        len(type_lists.enchantment),
        len(type_lists.spell),
    )


@app.command()
def download() -> Path:
    """Download latest Scryfall bulk data"""
    logger.info("Downloading bulk data files from Scryfall...")
    try:
        file_path = scryfall.download(get_paths().downloads)
    except scryfall.ScryfallError as e:
        logger.error("{}", e)
        if e.hint:
            logger.warning(e.hint)
        raise typer.Exit(1) from None
    logger.info("Download complete: {}", file_path)
    return file_path


@app.command()
def run(
    input_file: Annotated[
        Path | None,
        typer.Option(help="Path to Scryfall bulk data file (default: latest downloaded)"),
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
        typer.Option("--serve", "-s", help="Start HTTP server and open browser after generation"),
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
    paths = get_paths()
    if input_file is None:
        input_file = scryfall.find_latest_default_cards(paths.downloads)
        if input_file is None:
            logger.error("No 'default-cards' file found. Please run the download command.")
            raise typer.Exit(1)
    if output_folder is None:
        output_folder = paths.output / datetime.now().strftime("%Y%m%d_%H%M%S")

    generate(input_file, output_folder, only=only, exclude=exclude, dry_run=dry_run)

    if serve and not dry_run:
        serve_and_open_browser(output_folder)


def generate(
    input_file: Path,
    output_folder: Path,
    only: list[str] | None = None,
    exclude: list[str] | None = None,
    dry_run: bool = False,
) -> None:
    """Process a bulk data file and write the report site to `output_folder`."""
    paths = get_paths()
    type_lists = load_type_lists(paths.types_file)
    context = AggregatorContext(type_lists=type_lists, supercycles_file=paths.supercycles_file)
    aggregators = create_aggregators(context, only=only, exclude=exclude)
    if not aggregators:
        logger.warning(
            "No aggregators selected. Available: {}", [cls.name for cls in AGGREGATOR_CLASSES]
        )
        return

    logger.info("Input: {}", input_file.name)
    if dry_run:
        logger.info("DRY RUN - No files will be generated")
        for idx, agg in enumerate(aggregators, 1):
            logger.info("  {}. {} ({})", idx, agg.display_name, agg.name)
        logger.info("Total: {} aggregators would be processed", len(aggregators))
        return

    logger.info("Processing cards through {} aggregators...", len(aggregators))
    try:
        process_cards(scryfall.iter_cards(input_file), aggregators, type_lists)
    except TooManyErrors as e:
        logger.critical("{}", e)
        raise typer.Exit(1) from None

    reports = build_reports(aggregators)
    write_site(output_folder, reports, generated_at=datetime.now())

    for report in reports:
        logger.info("{}: {} records", report.aggregator.display_name, len(report.rows))

    seen_warnings = set()
    for agg in aggregators:
        for warning in agg.warnings:
            warning_text = f"[{agg.display_name}] {warning}"
            if warning_text not in seen_warnings:
                seen_warnings.add(warning_text)
                logger.warning(warning_text)

    logger.info("Output: {}", output_folder.resolve())


@app.command(name="all")
def run_all(
    serve: Annotated[bool, typer.Option(help="Start server after processing")] = True,
    skip_download: Annotated[bool, typer.Option(help="Skip downloading fresh data")] = False,
    skip_types: Annotated[bool, typer.Option(help="Skip updating type lists")] = False,
):
    """Run complete workflow: download, update-types, process, serve"""
    logger.info("Starting MTG Card Aggregator workflow")
    paths = get_paths()

    if not skip_download:
        logger.info("Downloading data...")
        download()

    if not skip_types:
        logger.info("Updating types...")
        try:
            update_types()
        except typer.Exit:
            if not paths.types_file.exists():
                raise
            logger.warning("Continuing with the existing {}", paths.types_file)

    input_file = scryfall.find_latest_default_cards(paths.downloads)
    if input_file is None:
        logger.error("No data file found. Please run with download enabled.")
        raise typer.Exit(1)

    output_folder = paths.output / datetime.now().strftime("%Y%m%d_%H%M%S")
    generate(input_file, output_folder)
    logger.info("Workflow complete!")

    if serve:
        serve_and_open_browser(output_folder)


@app.command(name="serve")
def serve_command(
    folder: Annotated[
        Path | None, typer.Argument(help="Site folder (default: latest in data/output/)")
    ] = None,
    port: Annotated[int, typer.Option(help="Port to listen on")] = 8000,
):
    """Serve a generated site locally and open it in the browser"""
    if folder is None:
        runs = sorted(p for p in get_paths().output.glob("*") if (p / "index.html").exists())
        if not runs:
            logger.error("No generated site found. Run the 'run' command first.")
            raise typer.Exit(1)
        folder = runs[-1]
    serve_and_open_browser(folder, port)


def serve_and_open_browser(directory: Path, port: int = 8000):
    """Serve the given directory on localhost and open the browser."""
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory.resolve()))

    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    except OSError as e:
        logger.warning("Port {} unavailable ({}); using a free port instead", port, e)
        httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]

    url = f"http://localhost:{port}/"

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
