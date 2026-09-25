"""Write the report site: a static single-page app plus JSON data files.

Output layout:

    index.html, app.js, styles.css   the single-page app (copied from mtg/static)
    manifest.json                    report list, metadata, and column definitions
    <report>.json                    each report's rows
    <report>.html                    redirect from the old per-report page URLs
"""

import json
import shutil
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import markdown

from mtg.pipeline import Report

STATIC_FOLDER = Path(__file__).parent / "static"
STATIC_FILES = ("index.html", "app.js", "styles.css")

_REDIRECT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <meta http-equiv="refresh" content="0; url=index.html#/{name}">
    <script>location.replace("index.html#/{name}" + location.search);</script>
  </head>
  <body><a href="index.html#/{name}">{title}</a></body>
</html>
"""


def report_manifest_entry(report: Report) -> dict[str, Any]:
    agg = report.aggregator
    return {
        "name": agg.name,
        "displayName": agg.display_name,
        "description": agg.description,
        # Explanations are trusted Markdown from this repository, rendered to HTML here.
        "explanationHtml": markdown.markdown(agg.explanation, extensions=["fenced_code", "tables"])
        if agg.explanation
        else "",
        "columnDefs": agg.column_defs,
        "typeFilters": agg.type_filters,
        "dataFile": f"{agg.name}.json",
        "rowCount": len(report.rows),
    }


def write_site(output_folder: Path, reports: list[Report], generated_at: datetime) -> None:
    output_folder.mkdir(parents=True, exist_ok=True)

    for name in STATIC_FILES:
        shutil.copyfile(STATIC_FOLDER / name, output_folder / name)

    manifest = {
        "generatedAt": generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        "reports": [report_manifest_entry(report) for report in reports],
    }
    _write_json(output_folder / "manifest.json", manifest)

    for report in reports:
        name = report.aggregator.name
        _write_json(output_folder / f"{name}.json", report.rows)
        (output_folder / f"{name}.html").write_text(
            _REDIRECT_TEMPLATE.format(name=name, title=escape(report.aggregator.display_name)),
            encoding="utf-8",
        )


def _write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
