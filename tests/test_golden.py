"""End-to-end test: run every aggregator over a fixture dataset and compare to saved output.

The fixture (tests/fixtures/sample_cards.jsonl) is a hand-written set of Scryfall-shaped
cards covering edge cases: double-faced cards, Kindred cards, mixed subtypes, tokens,
Un-cards, and so on. If a change alters report output on purpose, regenerate the
expected files with:

    UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py
"""

import gzip
import json
import os
import shutil
from pathlib import Path

import pytest

import card_aggregator

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent / "golden"


def _normalize(name, rows):
    # Unfinished supercycles are measured up to today, so drop the moving parts.
    if name == "supercycle_completion_time":
        for row in rows:
            if row["status"] == "Unfinished":
                row.pop("time")
                row.pop("days")
    return rows


@pytest.fixture(scope="module")
def reports(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("golden")
    downloads = tmp / "downloads"
    manual = tmp / "manual"
    downloads.mkdir()
    manual.mkdir()
    shutil.copy(FIXTURES / "all_creature_types.txt", downloads)
    shutil.copy(FIXTURES / "all_land_types.txt", downloads)
    shutil.copy(FIXTURES / "supercycles.yaml", manual)
    input_file = downloads / "default-cards-2026-01-01.jsonl.gz"
    with gzip.open(input_file, "wb") as f:
        f.write((FIXTURES / "sample_cards.jsonl").read_bytes())

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(card_aggregator, "DOWNLOADED_DATA_FOLDER", downloads)
        mp.setattr(card_aggregator, "MANUAL_DATA_FOLDER", manual)
        output = tmp / "output"
        card_aggregator.run_internal(
            input_file=input_file,
            output_folder=output,
            serve=False,
            only=None,
            exclude=None,
            dry_run=False,
        )

    names = [agg.name for agg in card_aggregator.create_all_aggregators()]
    return {
        name: _normalize(name, json.loads((output / f"{name}.json").read_text(encoding="utf-8")))
        for name in names
    }


def test_report_set_is_unchanged(reports):
    expected = sorted(p.stem for p in GOLDEN.glob("*.json"))
    if os.environ.get("UPDATE_GOLDEN"):
        return
    assert sorted(reports) == expected


def test_reports_match_golden(reports):
    mismatched = []
    for name, rows in reports.items():
        golden_file = GOLDEN / f"{name}.json"
        if os.environ.get("UPDATE_GOLDEN"):
            golden_file.write_text(
                json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            continue
        expected = json.loads(golden_file.read_text(encoding="utf-8"))
        if rows != expected:
            mismatched.append(name)
    assert mismatched == [], f"Reports differ from golden output: {mismatched}"
