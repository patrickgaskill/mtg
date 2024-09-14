from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
import orjson
import pandas as pd
import re
import requests
import time

DATA_PATH = Path("./data")


def fetch_scryfall_data():
    bulk_data = orjson.loads(requests.get("https://api.scryfall.com/bulk-data").text)
    download_uri = next(
        item["download_uri"]
        for item in bulk_data["data"]
        if item["type"] == "default_cards"
    )
    filename = download_uri.split("/")[-1]
    output_file = Path(DATA_PATH / filename)
    default_cards = requests.get(download_uri).content
    output_file.write_bytes(default_cards)


def open_latest_default_cards_file():
    def _get_timestamp(filename):
        return filename.split(".")[0].split("-")[2]

    files = DATA_PATH.glob("default-cards-*.json")
    sorted_files = sorted(files, key=lambda file: _get_timestamp(file.name))
    return open(sorted_files[-1], "r")


def make_output_dir():
    run_time = time.strftime("%Y-%m-%d-%H%M%S")
    output_path = DATA_PATH / "output" / run_time
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def get_sort_key(card):
    release_date = (
        datetime.fromisoformat(card["released_at"])
        if card["released_at"]
        else datetime.max
    )
    try:
        parsed_number = int(re.sub(r"[^\d]+", "", card["collector_number"]))
    except ValueError:
        parsed_number = 0
    return release_date, card["set"], parsed_number, card["collector_number"]


def generalize_mana_cost(mana_cost):
    """
    >>> generalize_mana_cost("{2}")
    '{2}'
    >>> generalize_mana_cost("{W}{W}")
    '{M}{M}'
    >>> generalize_mana_cost("{W}{U}{R}")
    '{M}{N}{O}'
    >>> generalize_mana_cost("{W}{U}{B}{R}{G}")
    '{W}{U}{B}{R}{G}'
    >>> generalize_mana_cost("{2/W}{2/U}")
    '{2/M}{2/N}'
    >>> generalize_mana_cost("{W/P}{W/U}{2/W}")
    '{M/P}{M/N}{2/M}'
    """
    generics = iter("MNOP")
    color_map = {}

    for c in mana_cost:
        if c in "WUBRG" and c not in color_map:
            try:
                color_map[c] = next(generics)
            except StopIteration:
                return mana_cost

    return mana_cost.translate(mana_cost.maketrans(color_map))


class Store:
    def __init__(self, name):
        self._store = {}
        self.name = name

    def evaluate(self, card):
        return self.add(card, None)

    def add(self, card, key):
        card["_sort_key"] = get_sort_key(card)

        if key in self._store:
            if card["_sort_key"] < self._store[key]["_sort_key"]:
                self._store[key] = card
                return True
        else:
            self._store[key] = card
            return True

        return False

    def dataframe(self):
        return pd.DataFrame.from_dict(self._store, orient="index")

    def to_html(self, output_dir, columns):
        with open(output_dir / f"{self.name}.html", "w") as f:
            self.dataframe().sort_values("_sort_key")[columns].to_html(f)

    def __len__(self):
        return len(self._store)


class PowerToughnessStore(Store):
    def __init__(self, name="power_toughness"):
        super().__init__(name)

    def evaluate(self, card):
        power = card["power"] if "power" in card else None
        toughness = card["toughness"] if "toughness" in card else None

        if power is None and toughness is None:
            return False

        key = (power, toughness)

        return self.add(card, key)

    def to_html(self, output_dir, columns=None):
        columns = columns or ["power", "toughness", "name", "set_name", "released_at"]
        return super().to_html(output_dir, columns)


class ManaCostStore(Store):
    def __init__(self, name="mana_cost"):
        super().__init__(name)

    def evaluate(self, card):
        if "mana_cost" not in card:
            return False

        if "card_faces" in card:
            card_was_added = False

            for card_face in card["card_faces"]:
                if "mana_cost" in card_face:
                    general_mana_cost = generalize_mana_cost(card_face["mana_cost"])
                    self.add(card, general_mana_cost)
                    card_was_added = True

            return card_was_added

        general_mana_cost = generalize_mana_cost(card["mana_cost"])
        return self.add(card, general_mana_cost)

    def to_html(self, output_dir, columns=None):
        columns = columns or ["mana_cost", "name", "set_name", "released_at"]
        return super().to_html(output_dir, columns)


def main():
    stores = [PowerToughnessStore(), ManaCostStore()]

    with open_latest_default_cards_file() as f:
        default_cards = orjson.loads(f.read())

    for card in default_cards:
        for store in stores:
            store.evaluate(card)

    output_dir = make_output_dir()

    for store in stores:
        store.to_html(output_dir)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("command", choices=["run", "update"])

    args = parser.parse_args()

    if args.command == "run":
        main()
    elif args.command == "update":
        fetch_scryfall_data()
