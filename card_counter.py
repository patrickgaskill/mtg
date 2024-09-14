import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import ijson
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.progress import wrap_file

from file_utils import download_default_cards, find_latest_default_cards


def update_counter(counters, counter_name, key, config, card):
    if config.get("max_field"):
        max_field = config["max_field"]
        max_value = card.get(max_field)
        if max_value is not None and max_value.isdigit():
            max_value = int(max_value)
            counters[counter_name][key]["max_value"] = max(
                counters[counter_name][key]["max_value"], max_value
            )
    else:
        counters[counter_name][key]["count"] += 1


def process_card(counters, counter_configs, card):
    for counter_name, config in counter_configs.items():
        key = config["condition"](card)
        if key:
            update_counter(counters, counter_name, key, config, card)


def generate_html_files(counters, counter_configs, output_folder, template_env):
    template = template_env.get_template("counter_template.html")
    for counter_name, counter in counters.items():
        config = counter_configs[counter_name]
        output_file = output_folder / f"{counter_name}.html"

        sorted_items = sorted(
            counter.items(),
            key=lambda x, config=config: x[1]["max_value"]
            if config.get("max_field")
            else x[1]["count"],
            reverse=True,
        )

        html_content = template.render(
            counter_name=counter_name,
            column_names=config["column_names"],
            sorted_items=sorted_items,
            max_field=config.get("max_field"),
            counters=counters,
        )

        with output_file.open("w") as file:
            file.write(html_content)


def count_cards(counter_configs, input_file, output_folder, template_env):
    counters = {name: defaultdict(lambda: defaultdict(int)) for name in counter_configs}

    with wrap_file(
        input_file.open("rb"),
        total=input_file.stat().st_size,
        description="Counting cards",
    ) as file:
        for card in ijson.items(file, "item"):
            process_card(counters, counter_configs, card)

    generate_html_files(counters, counter_configs, output_folder, template_env)


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Download and process card data.")
    parser.add_argument(
        "--download",
        action="store_true",
        help='Download the "default-cards" file from Scryfall.',
    )
    parser.add_argument(
        "--data-folder",
        type=str,
        default="data",
        help='The data folder where the "default-cards" file will be saved.',
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="Count cards based on the specified configurations.",
    )
    args = parser.parse_args()

    data_folder = Path(args.data_folder)

    # Set up rich console
    console = Console()

    # Download the "default-cards" file if the --download flag is set
    if args.download:
        input_file = download_default_cards(data_folder, console)
    else:
        input_file = find_latest_default_cards(data_folder)

    if input_file is None:
        console.print(
            "[red]No 'default-cards' file found. Please download the file using the --download flag.[/red]"
        )
        return

    # Set up Jinja template environment
    template_loader = FileSystemLoader(searchpath="./templates")
    template_env = Environment(loader=template_loader)

    # Count cards if the --count flag is set
    if args.count:
        # Define counter configurations
        counter_configs = {
            "card_finishes_by_name": {
                "condition": lambda card: card.get("name"),
                "column_names": ["Name", "Count"],
            },
            "card_finishes_by_name_set": {
                "condition": lambda card: (card.get("name"), card.get("set")),
                "column_names": ["Name", "Set", "Count"],
            },
            "max_collector_number_by_set": {
                "condition": lambda card: card.get("set"),
                "max_field": "collector_number",
                "column_names": ["Set", "Max Collector Number"],
            },
            # Add more counter configurations as needed
        }

        # Create output folder with timestamp inside the data folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_folder = data_folder / "output" / timestamp
        output_folder.mkdir(parents=True, exist_ok=True)

        # Count cards and populate counters
        count_cards(counter_configs, input_file, output_folder, template_env)
        console.print(
            "[green]Card counting complete. HTML files generated in the output folder.[/green]"
        )


if __name__ == "__main__":
    main()
