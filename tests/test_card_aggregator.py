"""Tests for card_aggregator download and data-file handling."""

import gzip
import json

import pytest
import responses
import typer

from aggregators import CountAggregator
from card_aggregator import (
    download,
    find_latest_default_cards,
    iter_cards,
    run_internal,
    update_types,
)


class TestIterCards:
    def test_reads_gzipped_jsonl(self, temp_dir, sample_cards_list):
        file_path = temp_dir / "default-cards-2026-07-29.jsonl.gz"
        with gzip.open(file_path, "wt", encoding="utf-8") as f:
            for card in sample_cards_list:
                f.write(json.dumps(card) + "\n")

        cards = list(iter_cards(file_path))
        assert cards == sample_cards_list

    def test_skips_blank_lines_in_jsonl(self, temp_dir, sample_card):
        file_path = temp_dir / "default-cards-2026-07-29.jsonl.gz"
        with gzip.open(file_path, "wt", encoding="utf-8") as f:
            f.write(json.dumps(sample_card) + "\n\n")

        cards = list(iter_cards(file_path))
        assert cards == [sample_card]

    def test_reads_legacy_json_array(self, temp_dir, sample_cards_list):
        file_path = temp_dir / "default-cards-2026-07-01.json"
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(sample_cards_list, f)

        cards = list(iter_cards(file_path))
        assert [card["name"] for card in cards] == [card["name"] for card in sample_cards_list]


class TestFindLatestDefaultCards:
    def test_returns_none_when_empty(self, temp_dir):
        assert find_latest_default_cards(temp_dir) is None

    def test_prefers_newest_date_across_formats(self, temp_dir):
        (temp_dir / "default-cards-2026-07-19.json").touch()
        (temp_dir / "default-cards-2026-07-29.jsonl.gz").touch()

        latest = find_latest_default_cards(temp_dir)
        assert latest is not None
        assert latest.name == "default-cards-2026-07-29.jsonl.gz"

    def test_compares_dates_across_months(self, temp_dir):
        (temp_dir / "default-cards-2026-06-30.jsonl.gz").touch()
        (temp_dir / "default-cards-2026-07-01.jsonl.gz").touch()

        latest = find_latest_default_cards(temp_dir)
        assert latest is not None
        assert latest.name == "default-cards-2026-07-01.jsonl.gz"


class TestDownload:
    @responses.activate
    def test_downloads_jsonl_gz(self, tmp_path, monkeypatch, mock_scryfall_response):
        monkeypatch.setattr("card_aggregator.DOWNLOADED_DATA_FOLDER", tmp_path)

        file_body = gzip.compress(b'{"name": "Lightning Bolt"}\n')
        entry = mock_scryfall_response["data"][0]
        entry["compressed_size"] = len(file_body)
        entry["updated_at"] = "2026-07-29T09:08:26.918+00:00"

        responses.add(
            responses.GET,
            "https://api.scryfall.com/bulk-data",
            json=mock_scryfall_response,
        )
        responses.add(responses.GET, entry["jsonl_download_uri"], body=file_body)

        file_path = download()

        assert file_path == tmp_path / "default-cards-2026-07-29.jsonl.gz"
        assert file_path.read_bytes() == file_body
        assert list(iter_cards(file_path)) == [{"name": "Lightning Bolt"}]

    @responses.activate
    def test_size_mismatch_leaves_no_data_file(self, tmp_path, monkeypatch, mock_scryfall_response):
        monkeypatch.setattr("card_aggregator.DOWNLOADED_DATA_FOLDER", tmp_path)

        file_body = gzip.compress(b'{"name": "Lightning Bolt"}\n')
        entry = mock_scryfall_response["data"][0]
        entry["compressed_size"] = len(file_body) + 1
        entry["updated_at"] = "2026-07-29T09:08:26.918+00:00"

        responses.add(
            responses.GET,
            "https://api.scryfall.com/bulk-data",
            json=mock_scryfall_response,
        )
        responses.add(responses.GET, entry["jsonl_download_uri"], body=file_body)

        with pytest.raises(typer.Exit):
            download()

        assert list(tmp_path.iterdir()) == []
        assert find_latest_default_cards(tmp_path) is None

    def test_partial_download_is_ignored(self, temp_dir):
        (temp_dir / "default-cards-2026-07-29.jsonl.gz.part").touch()
        (temp_dir / "default-cards-2026-07-28.jsonl.gz").touch()

        latest = find_latest_default_cards(temp_dir)
        assert latest is not None
        assert latest.name == "default-cards-2026-07-28.jsonl.gz"


class TestUpdateTypes:
    def test_creates_download_folder(self, tmp_path, monkeypatch):
        folder = tmp_path / "downloads"
        monkeypatch.setattr("card_aggregator.DOWNLOADED_DATA_FOLDER", folder)
        monkeypatch.setattr(
            "card_aggregator.fetch_and_parse_types", lambda: ({"Elf", "Human"}, {"Forest"})
        )

        update_types()

        assert (folder / "all_creature_types.txt").read_text() == "Elf\nHuman\n"
        assert (folder / "all_land_types.txt").read_text() == "Forest\n"

    def test_write_failure_exits_nonzero(self, tmp_path, monkeypatch):
        blocker = tmp_path / "downloads"
        blocker.write_text("not a folder")
        monkeypatch.setattr("card_aggregator.DOWNLOADED_DATA_FOLDER", blocker)
        monkeypatch.setattr("card_aggregator.fetch_and_parse_types", lambda: ({"Elf"}, {"Forest"}))

        with pytest.raises(typer.Exit) as exc_info:
            update_types()
        assert exc_info.value.exit_code == 1


class TestRunInternal:
    def test_writes_each_report_once(self, tmp_path, sample_cards_list, monkeypatch):
        input_file = tmp_path / "default-cards-2026-07-29.jsonl.gz"
        with gzip.open(input_file, "wt", encoding="utf-8") as f:
            for card in sample_cards_list:
                f.write(json.dumps(card) + "\n")

        calls = []
        original = CountAggregator.get_sorted_data

        def counting_get_sorted_data(self):
            calls.append(self.name)
            return original(self)

        monkeypatch.setattr(CountAggregator, "get_sorted_data", counting_get_sorted_data)

        output = tmp_path / "out"
        run_internal(
            input_file=input_file,
            output_folder=output,
            serve=False,
            only=["count_cards_by_name"],
            exclude=None,
            dry_run=False,
        )

        assert calls == ["count_cards_by_name"]
        rows = json.loads((output / "count_cards_by_name.json").read_text())
        assert {row["name"] for row in rows} == {card["name"] for card in sample_cards_list}
        html = (output / "count_cards_by_name.html").read_text()
        assert '<option value="count_cards_by_name.html" selected>' in html
