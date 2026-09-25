"""Tests for writing the report site."""

import json
from datetime import datetime

from mtg.aggregators.count_aggregators import FinishesByNameAggregator
from mtg.aggregators.type_aggregators import MaximalPrintedTypesAggregator
from mtg.pipeline import Report
from mtg.site import write_site


def test_writes_manifest_data_and_redirects(tmp_path):
    rows = [{"name": "Opt", "count": 2}]
    reports = [
        Report(FinishesByNameAggregator(), rows),
        Report(MaximalPrintedTypesAggregator(), []),
    ]

    write_site(tmp_path, reports, generated_at=datetime(2026, 1, 2, 3, 4, 5))

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["generatedAt"] == "2026-01-02 03:04:05"
    finishes, maximal = manifest["reports"]
    assert finishes["name"] == "count_finishes_by_name"
    assert finishes["dataFile"] == "count_finishes_by_name.json"
    assert finishes["rowCount"] == 1
    assert finishes["columnDefs"] == FinishesByNameAggregator().column_defs
    assert finishes["explanationHtml"].startswith("<p>")
    assert maximal["typeFilters"] == MaximalPrintedTypesAggregator.type_filters

    assert json.loads((tmp_path / "count_finishes_by_name.json").read_text()) == rows

    redirect = (tmp_path / "count_finishes_by_name.html").read_text()
    assert "index.html#/count_finishes_by_name" in redirect
    assert "location.search" in redirect  # keeps old ?field:keyword=0 filter links


def test_markdown_explanations_are_rendered(tmp_path):
    class Bold(FinishesByNameAggregator):
        explanation = "A **bold** claim."

    write_site(tmp_path, [Report(Bold(), [])], generated_at=datetime(2026, 1, 1))

    (entry,) = json.loads((tmp_path / "manifest.json").read_text())["reports"]
    assert entry["explanationHtml"] == "<p>A <strong>bold</strong> claim.</p>"
