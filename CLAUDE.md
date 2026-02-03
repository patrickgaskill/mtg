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
│   ├── constants.py         # Shared constants (foil types, dates, filters)
│   ├── count_aggregators.py # Generic counting, collector numbers
│   ├── first_card_aggregators.py # First cards by power/toughness, mana cost
│   ├── metadata_aggregators.py   # Illustrations, promo types, foil types
│   ├── supercycle_aggregators.py # Tracks completion times for card cycles
│   └── type_aggregators.py       # Complex type analysis with global effects
├── templates/               # Jinja2 HTML templates
│   ├── base_template.html  # AG Grid-based report page
│   └── index_template.html # Landing page with report list
├── data/                    # Data files (mostly gitignored)
│   ├── downloads/          # Scryfall JSON files (gitignored)
│   ├── manual/             # supercycles.yaml (tracked in git)
│   └── output/             # Generated HTML reports (gitignored)
├── card_aggregator.py      # Main CLI application (Typer)
├── card_utils.py           # Utility functions for card processing
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

**Key Points:**
- Each aggregator maintains its own internal state during processing
- `process_card()` is called for each card in the Scryfall data
- `get_sorted_data()` returns final results for HTML rendering
- Base class provides `generate_html()` method using Jinja2 templates
- Column definitions are specified via `self.column_defs` for AG Grid

### Card Filtering

Constants in `aggregators/constants.py` define what counts as "traditional" cards:
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
# Download latest Scryfall bulk data
uv run python card_aggregator.py download

# Update creature/land types from comprehensive rules
uv run python card_aggregator.py update-types

# Process cards and generate reports
uv run python card_aggregator.py run [--input-file PATH] [--output-dir PATH] [--serve]

# Options:
#   --input-file: Path to Scryfall JSON (auto-detects latest if omitted)
#   --output-dir: Output directory (default: data/output)
#   --serve: Start local HTTP server and open browser
```

## Common Tasks

### Adding a New Aggregator

1. Create new class in appropriate `aggregators/*.py` file
2. Inherit from `Aggregator` base class
3. Implement `process_card()` and `get_sorted_data()`
4. Define `column_defs` for AG Grid columns
5. Add instance to aggregators list in `card_aggregator.py:run()`

### Modifying HTML Output

- Edit `templates/base_template.html` for individual report pages
- Edit `templates/index_template.html` for landing page
- AG Grid configuration is in base_template.html JavaScript
- Column definitions come from aggregator's `column_defs` property

### Updating Constants

- Card filtering constants: `aggregators/constants.py`
- Foil types and special sets: `aggregators/constants.py`
- Basic land types: `card_utils.py:BASIC_LAND_TYPES`

### Working with Supercycles

Supercycles are defined in `data/manual/supercycles.yaml`:
```yaml
supercycles:
  - name: "Cycle Name"
    finished: true  # or false for ongoing
    cards:
      - "Card Name 1"
      - "Card Name 2"
```

## Data Flow

1. **Download** (`card_aggregator.py:download()`)
   - Fetches bulk data from Scryfall API
   - Saves to `data/downloads/`
   - Handles network errors gracefully

2. **Processing** (`card_aggregator.py:run()`)
   - Streams JSON using `ijson` for memory efficiency
   - Calls `process_card()` on each aggregator for each card
   - Aggregators maintain internal state

3. **Output** (`card_aggregator.py:run()`)
   - Calls `get_sorted_data()` on each aggregator
   - Generates HTML using Jinja2 templates
   - Creates index page with navigation
   - Writes to `data/output/`

4. **Deployment** (`.github/workflows/publish_html.yml`)
   - Runs daily via GitHub Actions
   - Downloads data, processes, deploys to GitHub Pages

## Testing Considerations

**Currently no tests exist.** When adding tests, consider:
- Unit tests for card utility functions (`card_utils.py`)
- Unit tests for type extraction and classification
- Integration tests for aggregator processing
- Mock Scryfall API responses for download tests
- Test with edge cases (multi-faced cards, Changelings, special characters)

## Dependencies

**Production dependencies:**
- **typer** - Modern CLI framework with rich terminal output
- **rich** - Beautiful terminal formatting and progress bars
- **ijson** - Streaming JSON parser for large files
- **requests** - HTTP library for API calls
- **jinja2** - Template engine for HTML generation
- **beautifulsoup4** - HTML parsing for comprehensive rules scraping
- **pyyaml** - YAML parsing for supercycles data

**Dev dependencies:**
- **ty** - Astral's extremely fast Python type checker
- **ruff** - Astral's extremely fast Python linter and formatter

Package management via **uv** (fast pip/poetry replacement).

## Important Quirks

1. **Time Lord Handling** - The creature type "Time Lord" contains a space and needs special handling in `extract_types()` - temporarily replace with hyphenated version for word boundary matching.

2. **Collector Number Sorting** - Collector numbers may contain letters (e.g., "123a"), so `get_sort_key()` strips non-digits for numeric sorting.

3. **Date Handling** - Cards without release dates get `datetime.max.date()` for sorting purposes.

4. **Supercycle Sorting** - Sort by actual day count (`days` field), not by parsing the formatted time string. This was a bug fixed in commit a03c957.

5. **Memory Efficiency** - Use `ijson` for streaming large JSON files rather than loading entire file into memory.

## Recent Changes

- **2025-11-20** - Code cleanup (commit a03c957):
  - Consolidated duplicate constants to `aggregators/constants.py`
  - Fixed supercycle sorting bug to use day count instead of string parsing
  - Added project name to pyproject.toml
  - Added docstring to `generate_nav_links()`

- **2025-11-20** - Migrated TODO items to GitHub Issues (#2-#11)

## GitHub Actions

Workflow file: `.github/workflows/publish_html.yml`

**Current behavior:**
- Runs daily on schedule
- Can be triggered manually
- Downloads fresh Scryfall data
- Generates reports
- Deploys to GitHub Pages

**Known issue:** Uses legacy GitHub Pages deployment strategy (Issue #2)

## Useful Links

- [Scryfall API Documentation](https://scryfall.com/docs/api)
- [Scryfall Bulk Data](https://scryfall.com/docs/api/bulk-data)
- [MTG Comprehensive Rules](https://magic.wizards.com/en/rules)
- [AG Grid Documentation](https://www.ag-grid.com/javascript-data-grid/)
- [GitHub Issues](https://github.com/patrickgaskill/mtg/issues)

## Working with This Project

**Before making changes:**
- Read relevant aggregator code to understand the pattern
- Check `aggregators/constants.py` for existing constants
- Use `is_traditional_card()` for filtering when appropriate
- Consider memory efficiency for large datasets

**Code style:**
- Use type hints
- Add docstrings to public functions
- Keep aggregators focused on single responsibility
- Use descriptive variable names
- Follow existing patterns for consistency

**Before committing:**
- **ALWAYS format code with ruff:** `uv run ruff format .`
- **ALWAYS typecheck with ty:** `uv run ty check`
- Write clear commit messages following existing style
- Reference issue numbers when applicable
- Test locally with `uv run python card_aggregator.py run --serve`
