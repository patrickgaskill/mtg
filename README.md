# MTG Card Data Aggregator

This project fetches Magic: The Gathering card data from Scryfall, processes it, and generates various HTML reports with interactive tables using AG Grid. The reports are automatically updated daily and published to GitHub Pages.

## Features

- Fetches the latest MTG card data from Scryfall
- Updates creature and land type lists from the latest MTG rules
- Generates interactive reports with sortable, filterable tables using AG Grid
- 23 reports, from card counts and foil types to creature type firsts, functional reprints, and maximal type lines (run `uv run mtg list` for all of them)
- Automatically updates and publishes reports daily

## Setup

1. Clone this repository
2. Install uv if you haven't already:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Install the project dependencies:

```
uv sync
```

## Usage

### Quick Start

The easiest way to run the complete workflow is:

```bash
uv run mtg all
```

This single command will:
1. Download the latest card data from Scryfall
2. Update creature and land types from MTG comprehensive rules
3. Process the data and generate all reports
4. Start a local web server and open your browser

### Available Commands

**📊 Check Status**
```bash
uv run mtg status
```
Shows information about downloaded data, type files, and available aggregators.

**📋 List Aggregators**
```bash
uv run mtg list
```
Displays all available aggregators in a formatted table.

**📥 Download Data**
```bash
uv run mtg download
```
Downloads the latest Scryfall bulk data file.

**🏷️ Update Types**
```bash
uv run mtg update-types
```
Updates the creature, land, artifact, enchantment, and spell type lists from the MTG comprehensive rules and saves them to `data/rules/types.json`. That file is committed so reports still work when the rules site is unavailable; commit it again after running this.

**⚙️ Generate Reports**
```bash
uv run mtg run [OPTIONS]
```
Processes card data and generates the report site.

**🌐 Serve Reports**
```bash
uv run mtg serve [FOLDER] [--port 8000]
```
Serves a generated site (default: the latest in `data/output/`) on localhost and opens it in your browser.

**🚀 Complete Workflow**
```bash
uv run mtg all [OPTIONS]
```
Runs the complete workflow: download → update-types → process → serve.

### Command Options

#### `run` Command

```bash
uv run mtg run --help
```

**Basic Options:**
- `--input-file PATH`: Specify a Scryfall bulk data file (`.jsonl.gz`, `.jsonl`, or `.json`; auto-detects latest if not specified)
- `-o, --output PATH`: Specify output directory (default: timestamped folder in `data/output/`)
- `-s, --serve`: Start HTTP server and open browser after generating files

**Filtering Options:**
- `--only <name>`: Run only specific aggregators (can specify multiple times)
- `--exclude <name>`: Exclude specific aggregators (can specify multiple times)
- `--dry-run`: Preview what would be generated without actually processing

**Examples:**

```bash
# Generate all reports and serve
uv run mtg run --serve

# Run only specific aggregators
uv run mtg run --only supercycle_completion_time --only foil_types_by_name

# Exclude certain aggregators
uv run mtg run --exclude count_cards_by_name --exclude count_finishes_by_name

# Preview what would be generated
uv run mtg run --dry-run

# Custom input and output
uv run mtg run --input-file data/downloads/custom.json -o data/output/custom
```

#### `all` Command

```bash
uv run mtg all --help
```

**Options:**
- `--serve / --no-serve`: Start server after processing (default: enabled)
- `--skip-download`: Skip downloading fresh data
- `--skip-types`: Skip updating type lists (if updating fails, the existing `data/rules/types.json` is used)

**Examples:**

```bash
# Complete workflow with all steps
uv run mtg all

# Skip download if you already have fresh data
uv run mtg all --skip-download

# Process only (skip download and type updates)
uv run mtg all --skip-download --skip-types

# Generate without serving
uv run mtg all --no-serve
```

#### Global Options

Available for all commands (put them before the command name, e.g. `uv run mtg -v run`):
- `-v, --verbose`: Show debug output
- `-q, --quiet`: Only show warnings and errors
- `--data-dir PATH`: Folder for downloaded and generated data (default: `data`)

### Output

The report site is saved to `./data/output/[timestamp]/` by default. It's a static single-page app:

- `index.html`, `app.js`, `styles.css`: the app, which lists the reports and shows each one in an AG Grid table
- `manifest.json`: every report's name, description, explanation, and column definitions
- `<report>.json`: each report's rows
- `<report>.html`: redirects from the old one-page-per-report URLs

Reports are addressed as `index.html#/<report>`, and type filter toggles are kept in the URL so filtered views can be shared. Tables are sortable and filterable, card names link to Scryfall with image previews, and the layout works on phones.

### Automated Updates

This repository is set up with GitHub Actions to automatically update the data and regenerate the reports daily. The workflow:

1. Runs at 09:00 UTC daily (4:00 AM or 5:00 AM ET, depending on daylight saving time)
2. Downloads the latest card data from Scryfall
3. Updates the creature and land type lists
4. Generates all reports
5. Publishes the reports to GitHub Pages

## Development

```bash
uv run pytest            # all tests
uv run ruff format .     # format
uv run ruff check .      # lint
uv run ty check          # type check
```

- `tests/test_golden.py` runs every report over a hand-written fixture dataset (`tests/fixtures/sample_cards.jsonl`) and compares the output to `tests/golden/`. If you change a report's output on purpose, regenerate the expected files with `UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py` and review the diff.
- `tests/test_real_sample.py` checks invariants over `tests/fixtures/scryfall_sample.jsonl.gz`, a few hundred real Scryfall cards. To refresh it and `data/rules/types.json`, run the **Refresh rules and test data** workflow from the Actions tab; it opens a pull request with any changes. Locally, `uv run mtg make-sample` does the same from your latest download.
- `tests/test_spa.py` drives the site in Chromium. Install it with `uv run playwright install chromium`; without it these tests are skipped locally (CI requires them).

To add a report, subclass `Aggregator` (or `FirstCardByKeyAggregator` for "first card per key" reports) in `mtg/aggregators/`, set its `name`, `display_name`, `description`, and `column_defs`, and add the class to `AGGREGATOR_CLASSES` in `mtg/aggregators/registry.py`.

## Viewing the Reports

The generated reports are available at: https://patrickgaskill.github.io/mtg/

## Technology Stack

- Python for data processing
- uv for dependency management
- AG Grid for interactive tables
- JSON for data storage
- A static single-page app (HTML/CSS/JavaScript, no build step) for presentation
- GitHub Actions for automation
- GitHub Pages for hosting

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).

## Acknowledgements

- Card data provided by Scryfall (https://scryfall.com/)
- Rules information from Wizards of the Coast (https://magic.wizards.com/)
- AG Grid for the interactive tables (https://www.ag-grid.com/)
