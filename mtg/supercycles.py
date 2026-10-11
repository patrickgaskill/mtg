"""Supercycle definitions (data/manual/supercycles.yaml) and the rules that spot new members.

Each supercycle lists its known cards. It can also carry a `match` rule describing
what a member looks like, so cards printed later that fit the rule are reported as
candidates for a person to confirm. Rules never add cards on their own.

    - name: Thirsts
      finished: false
      match:
        name: "^Thirst for \\w+$"   # regexes are searched, case-sensitive
        type: "^Instant$"
      cards: [...]

Rule keys (every key given must hold, on at least one printing):
    name, type, oracle, mana_cost: regexes searched in the card name, full type
        line, rules text of every face (which names the card itself, e.g. "Exile
        Rousing Refrain with..."), and mana cost
    keywords: keywords the card must have
    rarity: allowed rarities for the printing
    power, toughness: exact values
    exclude: card names that fit the rule but aren't members

`slots` names the members of a closed set (e.g. the 22 major arcana). A cycle with
slots is finished once every slot word appears in a listed card's name, so it
doesn't need `finished`.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from mtg.card import Card
from mtg.constants import NON_TRADITIONAL_LAYOUTS, NON_TRADITIONAL_PROMO_TYPES

RULE_KEYS = frozenset(
    {"name", "type", "oracle", "mana_cost", "keywords", "rarity", "power", "toughness", "exclude"}
)
CYCLE_KEYS = frozenset({"name", "finished", "cards", "match", "slots"})

# Printings that never count as new members: tokens and emblems, art cards,
# memorabilia (gold-bordered, oversized), and playtest cards.
IGNORED_LAYOUTS = frozenset({*NON_TRADITIONAL_LAYOUTS, "art_series"})
IGNORED_SET_TYPES = frozenset({"memorabilia", "token"})
# Alchemy rebalanced cards are named "A-<original name>".
REBALANCED_PREFIX = "A-"


def can_be_member(card: Card) -> bool:
    """Whether a printing could be a new supercycle member."""
    return not (
        card.layout in IGNORED_LAYOUTS
        or card.set_type in IGNORED_SET_TYPES
        or NON_TRADITIONAL_PROMO_TYPES.intersection(card.promo_types)
        or card.name.startswith(REBALANCED_PREFIX)
    )


def _pattern(value: Any, where: str) -> re.Pattern[str] | None:
    if value is None:
        return None
    try:
        return re.compile(str(value))
    except re.error as e:
        raise ValueError(f"{where}: bad regex {value!r}: {e}") from None


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


@dataclass(frozen=True)
class MatchRule:
    """What a supercycle member looks like; see the module docstring."""

    name: re.Pattern[str] | None = None
    type: re.Pattern[str] | None = None
    oracle: re.Pattern[str] | None = None
    mana_cost: re.Pattern[str] | None = None
    keywords: tuple[str, ...] = ()
    rarity: frozenset[str] = frozenset()
    power: str | None = None
    toughness: str | None = None
    exclude: frozenset[str] = frozenset()

    @classmethod
    def from_dict(cls, data: dict[str, Any], where: str) -> "MatchRule":
        if not isinstance(data, dict) or not data:
            raise ValueError(f"{where}: match must be a non-empty mapping")
        unknown = set(data) - RULE_KEYS
        if unknown:
            raise ValueError(f"{where}: unknown match keys {sorted(unknown)}")
        return cls(
            name=_pattern(data.get("name"), where),
            type=_pattern(data.get("type"), where),
            oracle=_pattern(data.get("oracle"), where),
            mana_cost=_pattern(data.get("mana_cost"), where),
            keywords=_strings(data.get("keywords")),
            rarity=frozenset(_strings(data.get("rarity"))),
            power=None if data.get("power") is None else str(data["power"]),
            toughness=None if data.get("toughness") is None else str(data["toughness"]),
            exclude=frozenset(_strings(data.get("exclude"))),
        )

    def matches(self, card: Card) -> bool:
        """Whether this printing fits the rule (exclusions aside)."""
        return (
            (self.name is None or bool(self.name.search(card.name)))
            and (self.type is None or bool(self.type.search(card.type_line)))
            and (self.oracle is None or bool(self.oracle.search(card.oracle_text)))
            and (self.mana_cost is None or bool(self.mana_cost.search(card.mana_cost)))
            and all(keyword in card.keywords for keyword in self.keywords)
            and (not self.rarity or card.rarity in self.rarity)
            and (self.power is None or card.power == self.power)
            and (self.toughness is None or card.toughness == self.toughness)
        )


@dataclass(frozen=True)
class Supercycle:
    name: str
    cards: tuple[str, ...]
    finished_flag: bool = False
    match: MatchRule | None = None
    slots: tuple[str, ...] = ()
    _slot_patterns: tuple[re.Pattern[str], ...] = field(default=(), repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Supercycle":
        if not isinstance(data, dict) or not data.get("name"):
            raise ValueError(f"Supercycle without a name: {data!r}")
        where = f"Supercycle '{data['name']}'"
        unknown = set(data) - CYCLE_KEYS
        if unknown:
            raise ValueError(f"{where}: unknown keys {sorted(unknown)}")
        slots = _strings(data.get("slots"))
        if "finished" not in data and not slots:
            raise ValueError(f"{where}: needs `finished` (or `slots`)")
        return cls(
            name=str(data["name"]),
            cards=_strings(data.get("cards")),
            finished_flag=bool(data.get("finished")),
            match=MatchRule.from_dict(data["match"], where) if "match" in data else None,
            slots=slots,
            _slot_patterns=tuple(
                re.compile(rf"\b{re.escape(slot)}\b", re.IGNORECASE) for slot in slots
            ),
        )

    @property
    def missing_slots(self) -> tuple[str, ...]:
        """Slots no listed card fills yet."""
        return tuple(
            slot
            for slot, pattern in zip(self.slots, self._slot_patterns, strict=True)
            if not any(pattern.search(card) for card in self.cards)
        )

    @property
    def finished(self) -> bool:
        if self.slots:
            return not self.missing_slots
        return self.finished_flag

    def is_candidate(self, card: Card) -> bool:
        """Whether a printing fits the rule but isn't listed or excluded."""
        return (
            self.match is not None
            and card.name not in self.cards
            and card.name not in self.match.exclude
            and can_be_member(card)
            and self.match.matches(card)
        )


def parse_supercycles(data: Any) -> list[Supercycle]:
    if not isinstance(data, dict) or not isinstance(data.get("supercycles"), list):
        raise ValueError("Expected a top-level `supercycles` list")
    cycles = [Supercycle.from_dict(entry) for entry in data["supercycles"]]
    seen: set[str] = set()
    for cycle in cycles:
        if cycle.name in seen:
            raise ValueError(f"Duplicate supercycle '{cycle.name}'")
        seen.add(cycle.name)
    return cycles


def load_supercycles(path: Path) -> list[Supercycle]:
    """Read supercycles from YAML. Raises OSError, yaml.YAMLError, or ValueError."""
    with path.open(encoding="utf-8") as f:
        return parse_supercycles(yaml.safe_load(f))


def member_names(cycles: Iterable[Supercycle]) -> set[str]:
    """Every card listed in any supercycle."""
    return {card for cycle in cycles for card in cycle.cards}
