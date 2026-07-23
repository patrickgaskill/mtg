"""Shared constants for aggregators."""

from datetime import datetime

# Network timeouts (seconds)
REQUEST_TIMEOUT = 30
RULES_FILE_TIMEOUT = 60

# HTTP request headers. Scryfall (and some other endpoints) reject requests
# that use the default python-requests User-Agent, returning HTTP 400/403.
# Scryfall's API guidelines require clients to send a User-Agent and Accept
# header; see https://scryfall.com/docs/api.
USER_AGENT = "mtg-card-aggregator/1.0"
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
}

# Sets where Scryfall invents collector numbers because the cards don't have
# real ones printed — e.g. Magic Online catalog IDs or event years. These are
# excluded from the max-collector-number report.
EXCLUDED_COLLECTOR_NUMBER_SETS = {
    "ana",  # Arena New Player Experience — Arena IDs
    "olgc",  # Legacy Championship — event years
    "ovnt",  # Vintage Championship — event years
    "pgpx",  # Grand Prix Promos — event years
    "pnat",  # Nationals Promos — event years
    "ppro",  # Pro Tour Promos — event years
    "prm",  # Magic Online Promos — Magic Online catalog IDs
    "pwor",  # World Championship Promos — event years
    "pz2",  # Treasure Chest — Magic Online catalog IDs
    "wmc",  # World Magic Cup Qualifiers — event years
}

# Card filtering constants
NON_TRADITIONAL_SET_TYPES = {"memorabilia", "funny"}
NON_TRADITIONAL_LAYOUTS = {"emblem", "token"}
NON_TRADITIONAL_BORDERS = {"silver", "gold"}
# Mystery Booster playtest cards (e.g. Orb of Origin) are mixed into the
# otherwise-traditional mb2 set, so they must be filtered by promo type.
NON_TRADITIONAL_PROMO_TYPES = {"playtest"}

# Foil-related constants
FOIL_PROMO_TYPES = {
    "confettifoil",
    "doublerainbow",
    "embossed",
    "galaxyfoil",
    "gilded",
    "halofoil",
    "invisibleink",
    "neonink",
    "oilslick",
    "rainbowfoil",
    "raisedfoil",
    "ripplefoil",
    "silverfoil",
    "stepandcompleat",
    "surgefoil",
    "textured",
}

MODERN_FOIL_CUTOFF_DATE = datetime(2003, 7, 28)  # Release date of 8th Edition

SPECIAL_FOIL_SETS = {
    "mps": "inventions",  # Kaladesh Inventions
    "mp2": "invocations",  # Amonkhet Invocations
    "exp": "expedition",  # Zendikar Expeditions
    "psus": "sunburst",  # Junior Super Series promos
    "dbl": "silverscreen",  # Innistrad Double Feature
}
