# Claude Code Context

This document provides context for AI assistants working on the MTG Card Aggregator project.

## Project Overview

A Python-based Magic: The Gathering card data aggregation and reporting tool that:
- Fetches bulk card data from Scryfall's API
- Processes and aggregates data in various ways
- Generates interactive HTML reports using AG Grid
- Publishes reports to GitHub Pages daily via GitHub Actions

**Live Site:** Deployed automatically to GitHub Pages
**Data Source:** Scryfall bulk data API
**Tech Stack:** Python 3.12+, Typer CLI, Jinja2, AG Grid

## Project Structure

```
mtg/
├── aggregators/              # Modular aggregator classes
│   ├── base.py              # Abstract base class for all aggregators
│   ├── count_aggregators.py # Generic counting, collector numbers
│   ├── first_card_aggregators.py # First cards by power/toughness, mana cost
│   ├── metadata_aggregators.py   # Illustrations, promo types, foil types
│   ├── supercycle_aggregators.py # Tracks completion times for card cycles
│   └── type_aggregators.py       # Complex type analysis with global effects
├── templates/               # Jinja2 HTML templates
│   ├── base_template.html  # AG Grid-based report page
│   └── index_template.html # Landing page with report list
├── tests/                   # Test suite
│   ├── conftest.py         # Shared pytest fixtures
│   ├── test_card_utils.py  # Tests for card utility functions
│   └── test_type_updater.py # Tests for type fetching
├── data/                    # Data files (mostly gitignored)
│   ├── downloads/          # Scryfall JSON files (gitignored)
│   ├── manual/             # supercycles.yaml (tracked in git)
│   └── output/             # Generated HTML reports (gitignored)
├── card_aggregator.py      # Main CLI application (Typer)
├── card_utils.py           # Utility functions for card processing
├── constants.py            # Shared constants (foil types, dates, filters)
├── type_updater.py         # Scrapes MTG comprehensive rules for types
├── pyproject.toml          # uv package manager configuration
└── README.md               # User-facing documentation
```

## Key Architecture Patterns

### Aggregator Pattern

All aggregators inherit from `aggregators/base.py:Aggregator`:

```python
class Aggregator(ABC):
    def __init__(self, name: str, display_name: str, description: str = "")

    @abstractmethod
    def process_card(self, card: Dict[str, Any]) -> None:
        """Process a single card and update internal state."""
        pass

    @abstractmethod
    def get_sorted_data(self) -> List[Dict[str, Any]]:
        """Return sorted results for HTML generation."""
        pass
```

Key points:
- Each aggregator maintains its own internal state during processing
- `process_card()` is called for each card in the Scryfall data
- `get_sorted_data()` returns final results for HTML rendering
- Base class provides `generate_html()` method using Jinja2 templates
- Column definitions are specified via `self.column_defs` for AG Grid
- Use `get_card_link_data(card)` from `card_utils` for Scryfall URI/image extraction

### Card Filtering

Constants in `constants.py` define what counts as "traditional" cards:
- `NON_TRADITIONAL_SET_TYPES` - memorabilia, funny sets
- `NON_TRADITIONAL_LAYOUTS` - emblems, tokens
- `NON_TRADITIONAL_BORDERS` - silver/gold borders

Use `card_utils.is_traditional_card()` to filter appropriately.

### Type Handling

Special considerations for creature/land types:
- "Time Lord" contains a space and requires special handling in regex
- `is_all_creature_types()` detects Changelings and Mistform Ultimus
- Types are extracted via `extract_types()` with careful word boundary matching
- Type data is updated from comprehensive rules via `type_updater.py`

## CLI Commands

```bash
uv run python card_aggregator.py download       # Download latest Scryfall bulk data
uv run python card_aggregator.py update-types    # Update types from comprehensive rules
uv run python card_aggregator.py run [--serve]   # Process cards and generate reports
uv run python card_aggregator.py all             # Full workflow: download → types → run → serve
```

## Data Flow

1. **Download** — Fetches bulk data from Scryfall API, saves to `data/downloads/`
2. **Processing** — Streams JSON via `ijson`, calls `process_card()` on each aggregator
3. **Output** — Generates HTML via Jinja2, writes to `data/output/`
4. **Deployment** — GitHub Actions runs daily, deploys to GitHub Pages

## Dependencies

**Production:** typer, loguru, ijson, requests, jinja2, beautifulsoup4, pyyaml, markdown
**Dev:** ruff, ty, pytest, pytest-cov, responses

Package management via **uv**.

## Important Quirks

1. **Time Lord Handling** — "Time Lord" contains a space; `extract_types()` temporarily hyphenates it for word boundary matching.
2. **Collector Number Sorting** — May contain letters (e.g., "123a"); `get_sort_key()` strips non-digits.
3. **Date Handling** — Cards without release dates get `datetime.max.date()` for sorting.
4. **Supercycle Sorting** — Sort by `days` field, not the formatted time string (bug fix: a03c957).
5. **Memory Efficiency** — Use `ijson` for streaming large JSON files.

## Before Committing

- `uv run pytest` — all tests must pass
- `uv run ruff format .` — format code
- `uv run ruff check .` — check for lint violations
