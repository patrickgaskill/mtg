"""Tests for the command-line interface."""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mtg import cli
from mtg.rules import TypeLists
from mtg.scryfall import ScryfallError

FIXTURES = Path(__file__).parent / "fixtures"
runner = CliRunner()


@pytest.fixture
def data_dir(tmp_path):
    """A data folder with type lists and supercycles in place."""
    (tmp_path / "rules").mkdir()
    (tmp_path / "manual").mkdir()
    shutil.copy(FIXTURES / "types.json", tmp_path / "rules" / "types.json")
    shutil.copy(FIXTURES / "supercycles.yaml", tmp_path / "manual" / "supercycles.yaml")
    return tmp_path


def invoke(data_dir, *args):
    return runner.invoke(cli.app, ["--data-dir", str(data_dir), *args])


class TestUpdateTypes:
    def test_writes_type_lists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            cli,
            "fetch_and_parse_types",
            lambda: TypeLists(creature=frozenset({"Elf"}), land=frozenset({"Forest"})),
        )

        result = invoke(tmp_path, "update-types")

        assert result.exit_code == 0, result.output
        saved = TypeLists.load(tmp_path / "rules" / "types.json")
        assert saved.creature == {"Elf"}
        assert saved.land == {"Forest"}

    def test_write_failure_exits_nonzero(self, tmp_path, monkeypatch):
        (tmp_path / "rules").write_text("not a folder")
        monkeypatch.setattr(cli, "fetch_and_parse_types", lambda: TypeLists())

        result = invoke(tmp_path, "update-types")

        assert result.exit_code == 1

    def test_fetch_failure_exits_nonzero(self, tmp_path, monkeypatch):
        def fail():
            raise ValueError("Network error while fetching rules page: offline")

        monkeypatch.setattr(cli, "fetch_and_parse_types", fail)

        assert invoke(tmp_path, "update-types").exit_code == 1


class TestDownload:
    def test_download_error_exits_nonzero(self, tmp_path, monkeypatch):
        def fail(_folder):
            raise ScryfallError("Network error", "Check your connection.")

        monkeypatch.setattr(cli.scryfall, "download", fail)

        assert invoke(tmp_path, "download").exit_code == 1


class TestRun:
    def test_generates_site(self, data_dir):
        output = data_dir / "site"

        result = invoke(
            data_dir, "run", "--input-file", str(FIXTURES / "sample_cards.jsonl"), "-o", str(output)
        )

        assert result.exit_code == 0, result.output
        manifest = json.loads((output / "manifest.json").read_text())
        names = [report["name"] for report in manifest["reports"]]
        assert names == [cls.name for cls in cli.AGGREGATOR_CLASSES]
        for name in names:
            assert (output / f"{name}.json").exists()
            assert (output / f"{name}.html").exists()
        for static_file in ("index.html", "app.js", "styles.css"):
            assert (output / static_file).exists()

    def test_only_filter(self, data_dir):
        output = data_dir / "site"

        result = invoke(
            data_dir,
            "run",
            "--input-file",
            str(FIXTURES / "sample_cards.jsonl"),
            "-o",
            str(output),
            "--only",
            "count_cards_by_name",
        )

        assert result.exit_code == 0, result.output
        manifest = json.loads((output / "manifest.json").read_text())
        assert [report["name"] for report in manifest["reports"]] == ["count_cards_by_name"]

    def test_dry_run_writes_nothing(self, data_dir):
        output = data_dir / "site"

        result = invoke(
            data_dir,
            "run",
            "--input-file",
            str(FIXTURES / "sample_cards.jsonl"),
            "-o",
            str(output),
            "--dry-run",
        )

        assert result.exit_code == 0, result.output
        assert not output.exists()

    def test_missing_input_exits_nonzero(self, tmp_path):
        assert invoke(tmp_path, "run").exit_code == 1


class TestAll:
    def test_continues_with_existing_types_when_update_fails(self, data_dir, monkeypatch):
        downloads = data_dir / "downloads"
        downloads.mkdir()
        shutil.copy(FIXTURES / "sample_cards.jsonl", downloads / "default-cards-2026-01-01.jsonl")

        def fail():
            raise ValueError("HTTP error while fetching rules page: 503")

        monkeypatch.setattr(cli, "fetch_and_parse_types", fail)

        result = invoke(data_dir, "all", "--skip-download", "--no-serve")

        assert result.exit_code == 0, result.output
        (site,) = (data_dir / "output").iterdir()
        assert (site / "manifest.json").exists()

    def test_stops_when_update_fails_without_existing_types(self, tmp_path, monkeypatch):
        def fail():
            raise ValueError("HTTP error while fetching rules page: 503")

        monkeypatch.setattr(cli, "fetch_and_parse_types", fail)

        result = invoke(tmp_path, "all", "--skip-download", "--no-serve")

        assert result.exit_code == 1
