"""End-to-end test: run every aggregator over a fixture dataset and compare to saved output.

The fixture (tests/fixtures/sample_cards.jsonl) is a hand-written set of Scryfall-shaped
cards covering edge cases: double-faced cards, Kindred cards, mixed subtypes, tokens,
Un-cards, and so on. If a change alters report output on purpose, regenerate the
expected files with:

    UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py
"""

import json
import os
import shutil
from pathlib import Path

import pytest

from mtg import cli
from mtg.aggregators import AGGREGATOR_CLASSES
from mtg.config import Paths

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
    paths = Paths(tmp_path_factory.mktemp("golden"))
    paths.types_file.parent.mkdir(parents=True)
    paths.manual.mkdir()
    shutil.copy(FIXTURES / "types.json", paths.types_file)
    shutil.copy(FIXTURES / "supercycles.yaml", paths.supercycles_file)
    output = paths.output / "site"

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cli._State, "paths", paths)
        cli.generate(FIXTURES / "sample_cards.jsonl", output)

    return {
        cls.name: _normalize(
            cls.name, json.loads((output / f"{cls.name}.json").read_text(encoding="utf-8"))
        )
        for cls in AGGREGATOR_CLASSES
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
