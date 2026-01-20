import re
from typing import Set, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout


def fetch_and_parse_types() -> Tuple[Set[str], Set[str]]:
    url = "https://magic.wizards.com/en/rules"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except (ConnectionError, Timeout) as e:
        raise ValueError(f"Network error while fetching rules page: {e}")
    except HTTPError as e:
        raise ValueError(f"HTTP error while fetching rules page: {e}")
    except RequestException as e:
        raise ValueError(f"Request error while fetching rules page: {e}")

    try:
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        raise ValueError(f"Error parsing rules page HTML: {e}")

    # Find all links to txt versions of the rules
    txt_links = soup.find_all("a", href=re.compile(r".*CompRules.*\.txt$"))
    if not txt_links:
        raise ValueError("Couldn't find the link to the comprehensive rules text file")

    # Try each TXT link until one works (sometimes the newest link is broken)
    rules_text = None
    errors = []

    for txt_link in txt_links:
        # Handle relative URLs; assume hrefs are already properly URL-encoded
        txt_url = urljoin(url, txt_link["href"])

        try:
            res = requests.get(txt_url, timeout=60)  # Longer timeout for large file
            res.raise_for_status()
            res.encoding = "utf-8"
            rules_text = res.text.replace("'", "'")
            break  # Success, stop trying other links
        except HTTPError as e:
            errors.append(f"HTTP error while downloading from {txt_url}: {e}")
            continue  # Try next link
        except (ConnectionError, Timeout) as e:
            errors.append(f"Network error while downloading from {txt_url}: {e}")
            continue  # Try next link
        except RequestException as e:
            errors.append(f"Request error while downloading from {txt_url}: {e}")
            continue  # Try next link

    if rules_text is None:
        error_summary = "\n".join(f"  - {error}" for error in errors)
        raise ValueError(
            f"Failed to download comprehensive rules after trying {len(txt_links)} link(s):\n{error_summary}"
        )

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
    creature_types.update(
        type.strip().replace("and ", "") for type in creature_types_text.split(",")
    )

    # Extract land types
    land_types_match = re.search(
        r"205\.3i Lands have their own unique set of subtypes; these subtypes are called land types\. The land types are (.*?)\. Of that list",
        rules_text,
        re.DOTALL,
    )
    if not land_types_match:
        raise ValueError("Couldn't find land types in the rules")

    land_types_text = land_types_match.group(1)

    # Handle land types, preserving "Power-Plant" and "Urza's"
    land_types = {
        type.strip().replace("and ", "") for type in land_types_text.split(",")
    }

    return creature_types, land_types
