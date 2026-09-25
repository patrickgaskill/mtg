# Claude Code Context

This document provides context for AI assistants working on the MTG Card Aggregator project.

## Project Overview

A Python-based Magic: The Gathering card data aggregation and reporting tool that:
- Fetches bulk card data from Scryfall's API
- Processes and aggregates data in various ways
- Publishes the results as a static single-page app (AG Grid tables over JSON files)
- Deploys to GitHub Pages daily via GitHub Actions

**Live Site:** Deployed automatically to GitHub Pages
**Data Source:** Scryfall bulk data API
**Tech Stack:** Python 3.12+, Typer CLI, vanilla JavaScript SPA, AG Grid

## Project Structure

```
mtg/
├── mtg/                      # The package (CLI entry point: `mtg`, or `python -m mtg`)
│   ├── cli.py               # Typer commands; wires the pieces below together
│   ├── config.py            # Paths: data folder layout
│   ├── scryfall.py          # Bulk data download, discovery, and streaming
│   ├── rules.py             # Comprehensive rules fetch/parse -> TypeLists (types.json)
│   ├── card.py              # Card/Face: normalized view of a Scryfall card
│   ├── card_utils.py        # Parsing helpers on raw card dicts (types, sort key, ...)
│   ├── constants.py         # Shared constants and fallback subtype lists
│   ├── pipeline.py          # Builds Cards, feeds aggregators, collects Reports
│   ├── site.py              # Writes manifest.json, report JSON, static app, redirects
│   ├── static/              # The SPA: index.html, app.js, styles.css (no build step)
│   └── aggregators/
│       ├── base.py          # Aggregator, FirstCardByKeyAggregator, AggregatorContext
│       ├── registry.py      # AGGREGATOR_CLASSES: every report, in site order
│       ├── count_aggregators.py
│       ├── creature_type_aggregators.py
│       ├── first_card_aggregators.py
│       ├── metadata_aggregators.py
│       ├── reprint_aggregators.py
│       ├── supercycle_aggregators.py
│       └── type_aggregators.py
├── tests/
│   ├── fixtures/            # sample_cards.jsonl (edge-case cards), types.json, supercycles.yaml
│   ├── golden/              # Expected rows for every report over the fixture cards
│   ├── helpers.py           # feed()/to_card()/type_context() for aggregator tests
│   ├── test_golden.py       # End-to-end: all reports vs tests/golden
│   ├── test_spa.py          # Playwright tests of the generated site
│   └── test_*.py            # Unit tests per module
├── data/
│   ├── downloads/           # Scryfall bulk data (gitignored)
│   ├── manual/              # supercycles.yaml (tracked)
│   ├── rules/               # types.json from `mtg update-types` (tracked as a fallback)
│   └── output/              # Generated sites (gitignored)
└── .github/workflows/       # ci.yml (lint, types, tests incl. browser), publish_html.yml (daily deploy)
```

## Key Architecture Patterns

### Cards

`Card.from_scryfall(raw, non_creature_subtypes, land_types)` is called once per card by the
pipeline. Aggregators only ever see `Card` objects, never raw Scryfall JSON. A `Card` resolves
layout differences up front:
- `card.faces`: real faces for multi-faced cards; one mirror face for single-faced cards, so
  code can always loop over faces
- `card.illustration_key`, `card.image_uri`, `face.image_uri`: art and images regardless of
  where Scryfall stored them
- `card.sort_key`, `card.is_traditional`, `card.types`, `card.creature_subtypes` (sorted
  tuple), `card.is_all_creature_types`: derived once
- `card.link(face)`: the `scryfall_uri`/`image_uri` pair report rows need

Cards are slim (slotted, only fields reports use), so aggregators can hold on to them.

### Aggregators

Every report is an `Aggregator` subclass with class-level metadata:

```python
class MyAggregator(Aggregator):
    name = "my_report"               # URL slug and JSON file name
    display_name = "My Report"
    description = "One line for the report list"
    explanation = "Optional **Markdown** shown above the grid"
    traditional_only = True          # runner skips non-traditional cards
    column_defs = [...]              # AG Grid columns
    type_filters = [...]             # optional checkbox toggles

    def process_card(self, card: Card) -> None: ...
    def get_sorted_data(self) -> list[dict]: ...
```

- Register new reports in `AGGREGATOR_CLASSES` (`aggregators/registry.py`); order there is site order.
- Constructors take one optional `AggregatorContext` (type lists, supercycles file, `today`).
- "First (or latest) card per key" reports subclass `FirstCardByKeyAggregator` and implement
  `keys(card)` (yield `(key, face)`) and `key_fields(key)`; `counts`, `extra_fields`,
  `sorted_items`, `prefer_latest`, and `image_from_face` cover the variations.
- Use `card_columns(header)` / `card_fields(card, face)` for the standard name/set/date columns.
- Aggregators never write files; `site.py` does.

### Site

`site.write_site` writes `manifest.json` (report metadata, column defs, explanations rendered
to HTML), one `<name>.json` per report, the static app from `mtg/static/`, and `<name>.html`
redirect stubs for old links. The app routes with the URL fragment (`#/<name>?field:keyword=0`)
so GitHub Pages serves every view from `index.html`. AG Grid, Popper, and Tippy load from CDNs
at pinned versions.

### Card Filtering

Constants in `constants.py` define what counts as "traditional" cards:
- `NON_TRADITIONAL_SET_TYPES` - memorabilia, funny sets
- `NON_TRADITIONAL_LAYOUTS` - emblems, tokens
- `NON_TRADITIONAL_BORDERS` - silver/gold borders
- `NON_TRADITIONAL_PROMO_TYPES` - playtest cards

`Card.is_traditional` applies them; set `traditional_only = True` rather than checking by hand.

### Type Handling

- Type lists come from the comprehensive rules via `mtg update-types` into `data/rules/types.json`
  (`TypeLists`: creature, land, artifact, enchantment, spell). The file is committed so runs work
  when the rules site is down; CI refreshes it in the workspace but doesn't commit it.
- Artifact/enchantment/spell/land lists fall back to `constants.py` when missing from the rules.
- `extract_creature_subtypes()` covers Kindred/Tribal cards and drops non-creature subtypes that
  share a type line (e.g. "Artifact Creature — Equipment Lizard").
- "Time Lord" contains a space and needs special handling in regexes.

## CLI Commands

```bash
uv run mtg download        # Download latest Scryfall bulk data
uv run mtg update-types    # Refresh data/rules/types.json from the comprehensive rules
uv run mtg run [--serve]   # Process cards and generate the site
uv run mtg serve           # Serve the latest generated site
uv run mtg all             # Full workflow: download → types → run → serve
uv run mtg -v run          # -v for debug logging, -q for warnings only, --data-dir to relocate data
```

## Data Flow

1. **Download**: `scryfall.download` fetches gzipped JSONL (`jsonl_download_uri`) into `data/downloads/`
2. **Processing**: `scryfall.iter_cards` streams raw cards; `pipeline.process_cards` builds a `Card`
   for each and passes it to the aggregators
3. **Output**: `pipeline.build_reports` collects rows once per aggregator; `site.write_site` writes the site
4. **Deployment**: GitHub Actions runs daily and deploys to GitHub Pages

## Dependencies

**Production:** typer, loguru, ijson, requests, beautifulsoup4, pyyaml, markdown
**Dev:** ruff, ty, pytest, pytest-cov, responses, playwright

Package management via **uv** (the project is an installable package; `uv sync` installs `mtg`).

## Important Quirks

1. **Time Lord Handling**: "Time Lord" contains a space; `extract_types()` temporarily hyphenates it for word boundary matching.
2. **Collector Number Sorting**: May contain letters (e.g., "123a"); `get_sort_key()` strips non-digits.
3. **Date Handling**: Cards without release dates get `date.max` for sorting.
4. **Supercycle Sorting**: Sort by `days` field, not the formatted time string (bug fix: a03c957).
5. **Double-Faced Cards**: Transform/MDFC cards keep `illustration_id`, `power`, `toughness`, and images on `card_faces`, not the top level. `Card` handles this; don't read raw JSON in aggregators.
6. **Downloads**: Written to `*.part` and renamed on success, so interrupted downloads are never picked up.
7. **Memory Efficiency**: Card data is streamed (gzipped JSONL line by line, legacy JSON arrays via `ijson`), and aggregators keep slim `Card` objects rather than raw JSON.
8. **Scryfall Bulk Format**: As of July 2026, Scryfall only offers bulk data as gzipped JSONL (`jsonl_download_uri` / `compressed_size`); the old `download_uri` / `size` fields are gone.
9. **Deterministic Output**: Never iterate a `set` of strings to produce report rows; string hashing is randomized per process, so order would change between runs. `creature_subtypes` is a sorted tuple for this reason.

## Before Committing

- `uv run pytest`: all tests must pass (golden test included; regenerate with `UPDATE_GOLDEN=1` only for intended output changes)
- `uv run ruff format .`: format code
- `uv run ruff check .`: check for lint violations
- `uv run ty check`: type check
