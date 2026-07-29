"""Tests for card_aggregator download and data-file handling."""

import gzip
import json

import responses

from card_aggregator import download, find_latest_default_cards, iter_cards


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
