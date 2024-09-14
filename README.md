# MTG Card Data Aggregator

This project fetches Magic: The Gathering card data from Scryfall, processes it, and generates various HTML reports. The reports are automatically updated daily and published to GitHub Pages.

## Features

- Fetches the latest MTG card data from Scryfall
- Updates creature and land type lists from the latest MTG rules
- Generates various reports including:
  - Cards by name
  - Finishes by name
  - Cards by set and name
  - Finishes by set and name
  - Card illustrations by set
  - Maximum collector number by set
  - Cards with maximal printed types
  - Promo types by card name
  - First card for each unique power/toughness combination
  - Foil types by card name
- Automatically updates and publishes reports daily

## Setup

1. Clone this repository
2. Install the required Python packages:
```
pip install -r requirements.txt
```

## Usage

### Local Usage

To run the aggregator locally:

1. Download the latest card data:
```
python card_aggregator.py download
```
2. Update the creature and land types:
```
python card_aggregator.py update-types
```
3. Generate the reports:
```
python card_aggregator.py run
```

The generated HTML files will be in the `./data/output` directory.

### Automated Updates

This repository is set up with GitHub Actions to automatically update the data and regenerate the reports daily. The workflow:

1. Runs at 09:00 UTC daily (4:00 AM or 5:00 AM ET, depending on daylight saving time)
2. Downloads the latest card data from Scryfall
3. Updates the creature and land type lists
4. Generates all reports
5. Publishes the reports to GitHub Pages

## Viewing the Reports

The generated reports are available at: https://patrickgaskill.github.io/mtg/

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).

## Acknowledgements

- Card data provided by Scryfall (https://scryfall.com/)
- Rules information from Wizards of the Coast (https://magic.wizards.com/)
