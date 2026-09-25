"""Tests for cutting the real-card test sample."""

import gzip
import json

from mtg import sample


def card(name, card_id, released_at="2020-01-01", **extra):
    return {
        "id": card_id,
        "name": name,
        "released_at": released_at,
        "set": "tst",
        "collector_number": "1",
        "prices": {"usd": "1.00"},
        "legalities": {"standard": "legal"},
        **extra,
    }


def test_keeps_earliest_printings_of_named_cards():
    printings = [card("Sol Ring", f"id-{year}", f"{year}-01-01") for year in range(2010, 2020)]

    selected = sample.build_sample(printings, names=["Sol Ring"])

    named = [c for c in selected if c["name"] == "Sol Ring"]
    assert [c["released_at"] for c in named][: sample.PRINTINGS_PER_NAME] == [
        f"{year}-01-01" for year in range(2010, 2010 + sample.PRINTINGS_PER_NAME)
    ]
    assert len(named) >= sample.PRINTINGS_PER_NAME


def test_random_slice_is_stable_and_about_the_right_size():
    cards = [card(f"Card {i}", f"id-{i}") for i in range(30_000)]

    first = sample.build_sample(cards, names=[])
    second = sample.build_sample(reversed(cards), names=[])

    assert first == second
    expected = len(cards) / sample.RANDOM_SAMPLE_RATE
    assert 0.7 * expected < len(first) < 1.3 * expected


def test_drops_unused_fields():
    (kept,) = sample.build_sample([card("Sol Ring", "id-1", type_line="Artifact")], ["Sol Ring"])

    assert "prices" not in kept
    assert "legalities" not in kept
    assert kept["type_line"] == "Artifact"


def test_written_sample_is_reproducible(tmp_path):
    cards = [card("Sol Ring", "id-1")]
    first, second = tmp_path / "a.jsonl.gz", tmp_path / "b.jsonl.gz"

    sample.write_sample(cards, first)
    sample.write_sample(cards, second)

    assert first.read_bytes() == second.read_bytes()
    with gzip.open(first, "rt", encoding="utf-8") as f:
        assert [json.loads(line) for line in f] == cards
