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

### Local Usage

To run the aggregator locally:

1. Download the latest card data:

```
uv run python card_aggregator.py download
```

2. Update the creature and land types:

```
uv run python card_aggregator.py update-types
```

3. Generate the reports:

```
uv run python card_aggregator.py run
```

The generated HTML and JSON files will be in the `./data/output/[timestamp]` directory.

### Command Options

The `run` command supports several options:

```
uv run python card_aggregator.py run --help
```

- `--input-file PATH`: Specify a custom Scryfall JSON file to use
- `--output-folder PATH`: Specify a custom output folder
- `--serve`: Start an HTTP server and open browser to view reports

Example with options:

```
uv run python card_aggregator.py run --serve
```

This will generate the reports and then start a local web server to view them in your browser.

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
