import re
from typing import Set, Tuple

import requests
from bs4 import BeautifulSoup


def fetch_and_parse_types() -> Tuple[Set[str], Set[str]]:
    url = "https://magic.wizards.com/en/rules"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Find the link to the txt version of the rules
    txt_link = soup.find("a", href=re.compile(r".*CompRules.*\.txt$"))
    if not txt_link:
        raise ValueError("Couldn't find the link to the comprehensive rules text file")

    txt_url = txt_link["href"]

    res = requests.get(txt_url)
    res.encoding = "utf-8"
    rules_text = res.text.replace("’", "'")

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
