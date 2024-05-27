from pathlib import Path

import requests
from rich.progress import (
    DownloadColumn,
    Progress,
)


def find_latest_default_cards(data_folder):
    """
    Find the latest "default-cards" file in the specified data folder based on the timestamp in the filename.

    Args:
        data_folder (Path): The path to the data folder.

    Returns:
        Path: The path to the latest "default-cards" file, or None if not found.
    """
    default_cards_files = list(data_folder.glob("default-cards-*.json"))
    if default_cards_files:
        latest_file = max(default_cards_files, key=lambda f: f.stem.split("-")[-1])
        return latest_file
    return None


def download_default_cards(data_folder, console):
    """
    Download the "default-cards" file from Scryfall and save it to the specified data folder.

    Args:
        data_folder (Path): The path to the data folder where the file will be saved.
        console (rich.console.Console): The rich console instance for output.

    Returns:
        Path: The path to the downloaded "default-cards" file.
    """
    # Download the list of bulk data files from Scryfall
    console.print("Downloading bulk data files from Scryfall...")
    response = requests.get("https://api.scryfall.com/bulk-data")
    bulk_data_files = response.json()["data"]

    # Find the "default-cards" file
    default_cards_file = next(
        file for file in bulk_data_files if file["type"] == "default_cards"
    )
    download_url = default_cards_file["download_uri"]
    file_name = Path(download_url).name

    # Download the "default-cards" file with progress bar
    response = requests.get(download_url, stream=True)

    data_folder.mkdir(parents=True, exist_ok=True)
    file_path = data_folder / file_name

    with Progress(*Progress.get_default_columns(), DownloadColumn()) as progress:
        task = progress.add_task(
            f"Downloading {default_cards_file["name"]}",
            filename=default_cards_file["name"],
            total=int(default_cards_file["size"]),
        )

        with file_path.open("wb") as file:
            for data in response.iter_content(chunk_size=1024):
                size = file.write(data)
                progress.update(task, advance=size)

    console.print(
        f"[green]Download complete:[/green] [bold]{file_path}[/bold]", highlight=False
    )
    return file_path
