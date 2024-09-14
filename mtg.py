from datetime import datetime
import orjson
import pandas as pd
import re

with open("./data/default-cards-20240520210708.json", "r") as f:
    default_cards = orjson.loads(f.read())


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


power_toughness_store = {}

for card in default_cards:
    power = card["power"] if "power" in card else None
    toughness = card["toughness"] if "toughness" in card else None
    if power is None and toughness is None:
        continue
    store_key = (power, toughness)
    if store_key in power_toughness_store:
        if get_sort_key(card) < get_sort_key(power_toughness_store[store_key]):
            power_toughness_store[store_key] = card
    else:
        power_toughness_store[store_key] = card

df = pd.DataFrame.from_dict(power_toughness_store, orient="index")

output = (
    df[["power", "toughness", "name", "set_name", "released_at"]]
    .sort_values("released_at")
    .reset_index(drop=True)
)

with open("./data/power_toughness.html", "w") as f:
    output.to_html(f)
