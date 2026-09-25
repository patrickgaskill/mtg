"""Fetch the comprehensive rules and extract type lists from them."""

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from loguru import logger
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from mtg.constants import (
    ARTIFACT_TYPES,
    ENCHANTMENT_TYPES,
    LAND_TYPES,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    RULES_FILE_TIMEOUT,
    SPELL_TYPES,
)

# Matches rules such as 205.3g: "...these subtypes are called artifact types. The
# artifact types are Attraction, Blood, ..., and Vehicle."
_SUBTYPE_LIST_PATTERN = re.compile(
    r"these subtypes are called (\w+) types\. The \1 types are (.*?)\.", re.DOTALL
)


@dataclass(frozen=True)
class TypeLists:
    """Subtype lists from the comprehensive rules.

    Creature and land types have no built-in fallback: when they are empty, the
    rules haven't been loaded and checks that need them are skipped. Artifact,
    enchantment, and spell types fall back to hand-maintained defaults.
    """

    creature: frozenset[str] = frozenset()
    land: frozenset[str] = frozenset()
    artifact: frozenset[str] = ARTIFACT_TYPES
    enchantment: frozenset[str] = ENCHANTMENT_TYPES
    spell: frozenset[str] = SPELL_TYPES

    @property
    def loaded(self) -> bool:
        return bool(self.creature and self.land)

    @property
    def non_creature_land_subtypes(self) -> frozenset[str]:
        """Subtypes that can share a type line with creature or land types."""
        return self.artifact | self.enchantment | self.spell

    @property
    def land_or_default(self) -> frozenset[str]:
        return self.land or LAND_TYPES

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {field: sorted(getattr(self, field)) for field in _FIELDS}
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "TypeLists":
        """Load type lists saved by `save`. Raises OSError or ValueError on failure."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{field: frozenset(data[field]) for field in _FIELDS if field in data})


_FIELDS = ("creature", "land", "artifact", "enchantment", "spell")


def _split_type_list(text: str) -> set[str]:
    """Split "A, B, and C" into {"A", "B", "C"}."""
    return {part.strip().removeprefix("and ").strip() for part in text.split(",")}


def fetch_and_parse_types() -> TypeLists:
    """Download the comprehensive rules and extract the type lists."""
    return parse_types(fetch_rules_text())


def fetch_rules_text() -> str:
    """Download the comprehensive rules as text, with curly quotes straightened."""
    url = "https://magic.wizards.com/en/rules"

    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except (ConnectionError, Timeout) as e:
        raise ValueError(f"Network error while fetching rules page: {e}") from None
    except HTTPError as e:
        raise ValueError(f"HTTP error while fetching rules page: {e}") from None
    except RequestException as e:
        raise ValueError(f"Request error while fetching rules page: {e}") from None

    try:
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        raise ValueError(f"Error parsing rules page HTML: {e}") from None

    # Find all links to txt versions of the rules
    txt_links = soup.find_all("a", href=re.compile(r".*CompRules.*\.txt$"))
    if not txt_links:
        raise ValueError("Couldn't find the link to the comprehensive rules text file")

    # Try each TXT link until one works (sometimes the newest link is broken)
    rules_text = None
    errors = []

    for i, txt_link in enumerate(txt_links):
        # Handle relative URLs; assume hrefs are already properly URL-encoded
        # Type check: ensure we have a Tag object with an href attribute
        if not isinstance(txt_link, Tag):
            continue
        href = txt_link.get("href")
        if href is None or not isinstance(href, str):
            continue
        txt_url = urljoin(url, href)

        try:
            res = requests.get(txt_url, headers=REQUEST_HEADERS, timeout=RULES_FILE_TIMEOUT)
            res.raise_for_status()
            res.encoding = "utf-8"
            rules_text = (
                res.text.replace("\u2018", "'")
                .replace("\u2019", "'")
                .replace("\u201c", '"')
                .replace("\u201d", '"')
            )
            break  # Success, stop trying other links
        except HTTPError as e:
            errors.append(f"HTTP error while downloading from {txt_url}: {e}")
        except (ConnectionError, Timeout) as e:
            errors.append(f"Network error while downloading from {txt_url}: {e}")
        except RequestException as e:
            errors.append(f"Request error while downloading from {txt_url}: {e}")

        # Brief delay before retrying next link
        if i < len(txt_links) - 1:
            time.sleep(1)

    if rules_text is None:
        error_summary = "\n".join(f"  - {error}" for error in errors)
        raise ValueError(
            f"Failed to download comprehensive rules after trying"
            f" {len(txt_links)} link(s):\n{error_summary}"
        )

    return rules_text


def parse_types(rules_text: str) -> TypeLists:
    """Extract the creature, land, artifact, enchantment, and spell type lists."""
    # Extract creature types
    creature_types_match = re.search(
        r"All other creature types are one word long: (.*?)\.", rules_text
    )
    if not creature_types_match:
        raise ValueError("Couldn't find creature types in the rules")

    creature_types_text = creature_types_match.group(1)

    # Extract "Time Lord" separately
    creature_types = {"Time Lord"}

    # Extract the rest of the types
    creature_types.update(_split_type_list(creature_types_text))

    # Extract land types
    land_types_match = re.search(
        r"205\.3i Lands have their own unique set of subtypes;"
        r" these subtypes are called land types\."
        r" The land types are (.*?)\. Of that list",
        rules_text,
        re.DOTALL,
    )
    if not land_types_match:
        raise ValueError("Couldn't find land types in the rules")

    land_types_text = land_types_match.group(1)

    # Handle land types, preserving "Power-Plant" and "Urza's"
    land_types = _split_type_list(land_types_text)

    if len(creature_types) < 50:
        raise ValueError(
            f"Suspiciously few creature types extracted ({len(creature_types)}); "
            "the rules page format may have changed"
        )
    if len(land_types) < 5:
        raise ValueError(
            f"Suspiciously few land types extracted ({len(land_types)}); "
            "the rules page format may have changed"
        )

    subtype_lists = {
        match.group(1): _split_type_list(match.group(2))
        for match in _SUBTYPE_LIST_PATTERN.finditer(rules_text)
    }

    def optional(category: str, default: frozenset[str]) -> frozenset[str]:
        found = subtype_lists.get(category)
        if not found:
            logger.warning("Couldn't find {} types in the rules; using built-in defaults", category)
            return default
        return frozenset(found)

    return TypeLists(
        creature=frozenset(creature_types),
        land=frozenset(land_types),
        artifact=optional("artifact", ARTIFACT_TYPES),
        enchantment=optional("enchantment", ENCHANTMENT_TYPES),
        spell=optional("spell", SPELL_TYPES),
    )
