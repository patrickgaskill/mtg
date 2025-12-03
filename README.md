# MTG Card Data Aggregator

This project fetches Magic: The Gathering card data from Scryfall, processes it, and generates various HTML reports with interactive tables using AG Grid. The reports are automatically updated daily and published to GitHub Pages.

## Features

- Fetches the latest MTG card data from Scryfall
- Updates creature and land type lists from the latest MTG rules
- Generates interactive reports with sortable, filterable tables using AG Grid
- Reports include:
  - Cards by name
  - Finishes by name
  - Cards by set and name
  - Finishes by set and name
  - Card illustrations by set
  - Maximum collector number by set
  - Cards with maximal printed types
  - Cards with maximal types considering global effects
  - Promo types by card name
  - First card for each unique power/toughness combination
  - Foil types by card name
  - Supercycle completion times
  - First cards by generalized mana cost
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
uv run python card_aggregator.py all
```

This single command will:
1. Download the latest card data from Scryfall
2. Update creature and land types from MTG comprehensive rules
3. Process the data and generate all reports
4. Start a local web server and open your browser

### Available Commands

**📊 Check Status**
```bash
uv run python card_aggregator.py status
```
Shows information about downloaded data, type files, and available aggregators.

**📋 List Aggregators**
```bash
uv run python card_aggregator.py list
```
Displays all available aggregators in a formatted table.

**📥 Download Data**
```bash
uv run python card_aggregator.py download
```
Downloads the latest Scryfall bulk data file.

**🏷️ Update Types**
```bash
uv run python card_aggregator.py update-types
```
Updates creature and land type lists from MTG comprehensive rules.

**⚙️ Generate Reports**
```bash
uv run python card_aggregator.py run [OPTIONS]
```
Processes card data and generates HTML reports.

**🚀 Complete Workflow**
```bash
uv run python card_aggregator.py all [OPTIONS]
```
Runs the complete workflow: download → update-types → process → serve.

### Command Options

#### `run` Command

```bash
uv run python card_aggregator.py run --help
```

**Basic Options:**
- `--input-file PATH`: Specify a custom Scryfall JSON file (auto-detects latest if not specified)
- `-o, --output PATH`: Specify output directory (default: timestamped folder in `data/output/`)
- `-s, --serve`: Start HTTP server and open browser after generating files

**Filtering Options:**
- `--only <name>`: Run only specific aggregators (can specify multiple times)
- `--exclude <name>`: Exclude specific aggregators (can specify multiple times)
- `--dry-run`: Preview what would be generated without actually processing

**Examples:**

```bash
# Generate all reports and serve
uv run python card_aggregator.py run --serve

# Run only specific aggregators
uv run python card_aggregator.py run --only supercycle_completion_time --only foil_types_by_name

# Exclude certain aggregators
uv run python card_aggregator.py run --exclude count_cards_by_name --exclude count_finishes_by_name

# Preview what would be generated
uv run python card_aggregator.py run --dry-run

# Custom input and output
uv run python card_aggregator.py run --input-file data/downloads/custom.json -o data/output/custom
```

#### `all` Command

```bash
uv run python card_aggregator.py all --help
```

**Options:**
- `--serve / --no-serve`: Start server after processing (default: enabled)
- `--skip-download`: Skip downloading fresh data
- `--skip-types`: Skip updating creature/land types

**Examples:**

```bash
# Complete workflow with all steps
uv run python card_aggregator.py all

# Skip download if you already have fresh data
uv run python card_aggregator.py all --skip-download

# Process only (skip download and type updates)
uv run python card_aggregator.py all --skip-download --skip-types

# Generate without serving
uv run python card_aggregator.py all --no-serve
```

#### Global Options

Available for all commands:
- `-v, --verbose`: Show detailed output
- `-q, --quiet`: Minimal output

### Output

Generated HTML and JSON files are saved to `./data/output/[timestamp]/` by default.

The reports feature:
- Interactive sortable and filterable tables powered by AG Grid
- Responsive design for desktop and mobile
- Navigation between different aggregator reports
- Timestamped generation information

### Automated Updates

This repository is set up with GitHub Actions to automatically update the data and regenerate the reports daily. The workflow:

1. Runs at 09:00 UTC daily (4:00 AM or 5:00 AM ET, depending on daylight saving time)
2. Downloads the latest card data from Scryfall
3. Updates the creature and land type lists
4. Generates all reports
5. Publishes the reports to GitHub Pages

## Viewing the Reports

The generated reports are available at: https://patrickgaskill.github.io/mtg/

## Technology Stack

- Python for data processing
- uv for dependency management
- AG Grid for interactive tables
- JSON for data storage
- HTML/CSS for presentation
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
