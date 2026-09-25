"""Download and read Scryfall bulk card data."""

import gzip
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import ijson
import requests
from loguru import logger
from requests.exceptions import (
    ChunkedEncodingError,
    ConnectionError,
    HTTPError,
    RequestException,
    Timeout,
)

from mtg.constants import REQUEST_HEADERS, REQUEST_TIMEOUT

BULK_DATA_URL = "https://api.scryfall.com/bulk-data"
DATA_FILE_PATTERNS = ("default-cards-*.json", "default-cards-*.jsonl", "default-cards-*.jsonl.gz")


class ScryfallError(Exception):
    """A download failed. `hint` suggests what the user can do about it."""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


def download(dest_folder: Path) -> Path:
    """Download the latest default-cards bulk file into `dest_folder`.

    The file is written to a temporary `.part` name and renamed only once complete,
    so an interrupted download never looks like a valid data file.
    """
    network_hint = "Please check your internet connection and try again."
    format_hint = "The Scryfall API response format may have changed."

    try:
        response = requests.get(BULK_DATA_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        bulk_data_files = response.json()["data"]
    except (ConnectionError, Timeout) as e:
        raise ScryfallError(
            f"Network error while fetching bulk data list: {e}", network_hint
        ) from e
    except HTTPError as e:
        raise ScryfallError(
            f"HTTP error while fetching bulk data list: {e}",
            "The Scryfall API may be temporarily unavailable.",
        ) from e
    except RequestException as e:
        raise ScryfallError(f"Request error while fetching bulk data list: {e}") from e
    except (KeyError, json.JSONDecodeError) as e:
        raise ScryfallError(f"Error parsing bulk data response: {e}", format_hint) from e

    entry = next((f for f in bulk_data_files if f.get("type") == "default_cards"), None)
    if entry is None:
        raise ScryfallError("Could not find default_cards file in bulk data list")

    # Scryfall retired the plain-JSON download_uri in July 2026; bulk data is
    # now only offered as gzipped JSONL via jsonl_download_uri.
    try:
        download_url = entry["jsonl_download_uri"]
        total_size = int(entry["compressed_size"])
        file_name = f"default-cards-{entry['updated_at'][:10]}.jsonl.gz"
    except KeyError as e:
        raise ScryfallError(f"Bulk data entry is missing expected field: {e}", format_hint) from e

    dest_folder.mkdir(parents=True, exist_ok=True)
    file_path = dest_folder / file_name
    part_path = file_path.with_name(file_path.name + ".part")

    try:
        response = requests.get(
            download_url, headers=REQUEST_HEADERS, stream=True, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except (ConnectionError, Timeout) as e:
        raise ScryfallError(f"Network error while downloading file: {e}", network_hint) from e
    except HTTPError as e:
        raise ScryfallError(
            f"HTTP error while downloading file: {e}",
            "The download URL may be invalid or the file may be temporarily unavailable.",
        ) from e
    except RequestException as e:
        raise ScryfallError(f"Request error while downloading file: {e}") from e

    logger.info(
        "Downloading {} ({:.1f} MB compressed)...",
        entry.get("name", file_name),
        total_size / (1024 * 1024),
    )

    try:
        with part_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                file.write(chunk)
    except ChunkedEncodingError as e:
        part_path.unlink(missing_ok=True)
        raise ScryfallError(
            f"Connection lost during download: {e}",
            "The download was interrupted. Please try again.",
        ) from e
    except (ConnectionError, Timeout) as e:
        part_path.unlink(missing_ok=True)
        raise ScryfallError(f"Network error during download: {e}", network_hint) from e
    except OSError as e:
        part_path.unlink(missing_ok=True)
        raise ScryfallError(
            f"Error writing file to disk: {e}", "Please check disk space and write permissions."
        ) from e

    actual_size = part_path.stat().st_size
    if actual_size != total_size:
        part_path.unlink()
        raise ScryfallError(
            f"Download size mismatch: got {actual_size} bytes, expected {total_size} bytes"
        )

    part_path.replace(file_path)
    return file_path


def find_latest_default_cards(data_folder: Path) -> Path | None:
    """Find the "default-cards" file with the newest date in its name, if any."""
    default_cards_files = [
        file for pattern in DATA_FILE_PATTERNS for file in data_folder.glob(pattern)
    ]

    def date_key(file: Path) -> str:
        match = re.search(r"\d{4}-\d{2}-\d{2}", file.name)
        return match.group() if match else ""

    return max(default_cards_files, key=date_key, default=None)


def iter_cards(input_file: Path) -> Iterator[dict[str, Any]]:
    """
    Stream card objects from a Scryfall bulk data file.

    Supports gzipped JSONL (.jsonl.gz, the current Scryfall format), plain JSONL
    (.jsonl), and legacy JSON arrays (.json).
    """
    if input_file.name.endswith((".jsonl.gz", ".jsonl")):
        opener = gzip.open if input_file.name.endswith(".gz") else open
        with opener(input_file, "rt", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    yield json.loads(line)
    else:
        with input_file.open("rb") as file:
            yield from ijson.items(file, "item")
