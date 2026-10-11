"""Tests for supercycle rules and new-member candidates."""

import json
from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from mtg import cli
from mtg.aggregators import AggregatorContext
from mtg.aggregators.supercycle_aggregators import SupercycleTimeAggregator
from mtg.supercycles import MatchRule, Supercycle, load_supercycles, parse_supercycles
from tests.helpers import feed, to_card

ROOT = Path(__file__).parent.parent


def raw(name, released_at="2020-01-01", **fields):
    return {
        "name": name,
        "set": "tst",
        "set_type": "expansion",
        "layout": "normal",
        "border_color": "black",
        "rarity": "rare",
        "released_at": released_at,
        "scryfall_uri": f"https://scryfall.com/card/tst/{name}",
        "type_line": "Instant",
        "oracle_text": "",
        **fields,
    }


THIRSTS = {
    "name": "Thirsts",
    "finished": False,
    "match": {"name": r"^Thirst for \w+$", "type": "^Instant$", "exclude": ["Thirst for Blood"]},
    "cards": ["Thirst for Knowledge", "Thirst for Meaning"],
}


def aggregator(tmp_path, *cycles):
    path = tmp_path / "supercycles.yaml"
    path.write_text(yaml.safe_dump({"supercycles": list(cycles)}))
    context = AggregatorContext(supercycles_file=path, today=lambda: date(2026, 1, 1))
    return SupercycleTimeAggregator(context)


class TestMatchRule:
    def test_every_given_key_must_hold(self):
        rule = MatchRule.from_dict(
            {
                "name": "^Mogg",
                "type": "^Creature",
                "mana_cost": r"^\{R\}\{R\}\{R\}$",
                "power": 3,
                "toughness": 3,
                "rarity": ["uncommon"],
            },
            "test",
        )
        mob = raw(
            "Mogg Mob",
            type_line="Creature — Goblin",
            mana_cost="{R}{R}{R}",
            power="3",
            toughness="3",
            rarity="uncommon",
        )

        assert rule.matches(to_card(mob))
        assert not rule.matches(to_card({**mob, "rarity": "rare"}))
        assert not rule.matches(to_card({**mob, "power": "2"}))
        assert not rule.matches(to_card({**mob, "mana_cost": "{2}{R}"}))

    def test_oracle_and_keywords(self):
        rule = MatchRule.from_dict(
            {"oracle": "with three time counters", "keywords": ["Suspend"]}, "test"
        )
        card = raw("Refrain", oracle_text="Exile Refrain with three time counters on it.")

        assert rule.matches(to_card({**card, "keywords": ["Suspend"]}))
        assert not rule.matches(to_card(card))

    def test_rejects_unknown_keys_and_bad_regexes(self):
        with pytest.raises(ValueError, match="unknown match keys"):
            MatchRule.from_dict({"colour": "U"}, "test")
        with pytest.raises(ValueError, match="bad regex"):
            MatchRule.from_dict({"name": "("}, "test")


class TestSupercycle:
    def test_needs_finished_or_slots(self):
        with pytest.raises(ValueError, match="needs `finished`"):
            Supercycle.from_dict({"name": "X", "cards": []})

    def test_slots_decide_finished(self):
        cycle = Supercycle.from_dict(
            {"name": "Stones", "slots": ["Soul", "Mind"], "cards": ["The Soul Stone"]}
        )
        assert not cycle.finished
        assert cycle.missing_slots == ("Mind",)

        done = Supercycle.from_dict(
            {
                "name": "Stones",
                "slots": ["Soul", "Mind"],
                "cards": ["The Soul Stone", "The Mind Stone"],
            }
        )
        assert done.finished

    def test_slots_match_whole_words(self):
        cycle = Supercycle.from_dict(
            {"name": "Arcana", "slots": ["Sun"], "cards": ["Sunny, the Fool"]}
        )
        assert cycle.missing_slots == ("Sun",)

    def test_rejects_duplicate_names(self):
        entry = {"name": "X", "finished": True, "cards": []}
        with pytest.raises(ValueError, match="Duplicate"):
            parse_supercycles({"supercycles": [entry, entry]})


class TestCandidates:
    def test_reports_unlisted_matches_once_with_earliest_printing(self, tmp_path):
        agg = aggregator(tmp_path, THIRSTS)

        feed(
            agg,
            raw("Thirst for Knowledge"),
            raw("Thirst for Meaning"),
            raw("Thirst for Discovery", "2022-02-18"),
            raw("Thirst for Discovery", "2021-09-24"),
            raw("Thirst for Blood"),  # excluded
            raw("Thirst for More", type_line="Sorcery"),  # wrong type
        )

        rows = agg.candidate_rows()
        assert [(r["supercycle"], r["name"], r["releaseDate"]) for r in rows] == [
            ("Thirsts", "Thirst for Discovery", "2021-09-24")
        ]
        agg.get_sorted_data()
        assert any("Thirst for Discovery" in w for w in agg.warnings)

    @pytest.mark.parametrize(
        "fields",
        [
            {"layout": "token"},
            {"layout": "art_series"},
            {"set_type": "memorabilia"},
            {"promo_types": ["playtest"]},
            {"name": "A-Thirst for Discovery"},
        ],
    )
    def test_ignores_printings_that_cannot_be_members(self, tmp_path, fields):
        agg = aggregator(tmp_path, {**THIRSTS, "match": {"type": "^Instant$"}})

        feed(agg, {**raw("Thirst for Discovery"), **fields})

        assert agg.candidate_rows() == []

    def test_flags_listed_cards_the_rule_misses(self, tmp_path):
        agg = aggregator(tmp_path, THIRSTS)

        feed(agg, raw("Thirst for Knowledge"), raw("Thirst for Meaning", type_line="Sorcery"))

        assert agg.unmatched_members() == [("Thirsts", "Thirst for Meaning")]

    def test_cycles_without_rules_have_no_candidates(self, tmp_path):
        agg = aggregator(tmp_path, {"name": "Plain", "finished": True, "cards": ["Opt"]})

        feed(agg, raw("Opt"), raw("Thirst for Discovery"))

        assert agg.candidate_rows() == []
        assert agg.unmatched_members() == []

    def test_slot_cycle_status_comes_from_slots(self, tmp_path):
        agg = aggregator(
            tmp_path,
            {"name": "Stones", "slots": ["Soul"], "cards": ["The Soul Stone"]},
        )

        feed(agg, raw("The Soul Stone"))

        assert agg.get_sorted_data()[0]["status"] == "Finished"

    def test_bad_file_becomes_a_warning(self, tmp_path):
        agg = aggregator(tmp_path, {"name": "X", "cards": []})

        assert agg.supercycles == []
        assert any("needs `finished`" in w for w in agg.warnings)


class TestCandidatesCommand:
    def write_cards(self, tmp_path, *cards):
        path = tmp_path / "cards.jsonl"
        path.write_text("".join(json.dumps(card) + "\n" for card in cards))
        return path

    def test_writes_markdown_for_candidates(self, tmp_path):
        (tmp_path / "manual").mkdir()
        (tmp_path / "manual" / "supercycles.yaml").write_text(
            yaml.safe_dump({"supercycles": [THIRSTS]})
        )
        cards = self.write_cards(tmp_path, raw("Thirst for Knowledge"), raw("Thirst for Discovery"))
        out = tmp_path / "candidates.md"

        result = cli_invoke(tmp_path, "--input-file", str(cards), "--markdown", str(out))

        assert result.exit_code == 0, result.output
        body = out.read_text()
        assert "| Thirsts | [Thirst for Discovery](https://scryfall.com/card/tst/" in body
        assert "Thirst for Meaning" not in body  # not seen, so not flagged

    def test_empty_markdown_when_nothing_found(self, tmp_path):
        (tmp_path / "manual").mkdir()
        (tmp_path / "manual" / "supercycles.yaml").write_text(
            yaml.safe_dump({"supercycles": [THIRSTS]})
        )
        cards = self.write_cards(tmp_path, raw("Thirst for Knowledge"))
        out = tmp_path / "candidates.md"

        result = cli_invoke(tmp_path, "--input-file", str(cards), "--markdown", str(out))

        assert result.exit_code == 0, result.output
        assert out.read_text() == ""

    def test_bad_supercycles_file_exits_nonzero(self, tmp_path):
        (tmp_path / "manual").mkdir()
        (tmp_path / "manual" / "supercycles.yaml").write_text("supercycles: [{name: X}]")
        cards = self.write_cards(tmp_path, raw("Opt"))

        assert cli_invoke(tmp_path, "--input-file", str(cards)).exit_code == 1


def cli_invoke(data_dir, *args):
    return CliRunner().invoke(
        cli.app, ["--data-dir", str(data_dir), "supercycle-candidates", *args]
    )


def test_project_supercycles_file_loads():
    cycles = load_supercycles(ROOT / "data" / "manual" / "supercycles.yaml")

    unfinished_without_rules = [c.name for c in cycles if not c.finished and c.match is None]
    assert unfinished_without_rules == []
    # Exclusions and listed cards must be real names, e.g. no YAML-escaped apostrophes.
    names = {n for c in cycles for n in c.cards} | {
        n for c in cycles if c.match for n in c.match.exclude
    }
    assert not [n for n in names if "''" in n]
