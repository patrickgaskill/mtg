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

# Subtypes that belong to non-creature, non-land card types (CR 205.3g, 205.3h,
# 205.3k). They can share a type line with creature or land subtypes, e.g.
# "Artifact Creature — Equipment Lizard" or "Enchantment Land — Urza's Saga",
# so they must be told apart from creature and land types. Update these lists
# when the comprehensive rules add a new artifact, enchantment, or spell type.
ARTIFACT_TYPES = {
    "Attraction",
    "Blood",
    "Bobblehead",
    "Clue",
    "Contraption",
    "Equipment",
    "Food",
    "Fortification",
    "Gold",
    "Incubator",
    "Infinity",
    "Junk",
    "Lander",
    "Map",
    "Mutagen",
    "Powerstone",
    "Spacecraft",
    "Treasure",
    "Vehicle",
}
ENCHANTMENT_TYPES = {
    "Aura",
    "Background",
    "Cartouche",
    "Case",
    "Class",
    "Curse",
    "Role",
    "Room",
    "Rune",
    "Saga",
    "Shard",
    "Shrine",
}
SPELL_TYPES = {"Adventure", "Arcane", "Chorus", "Lesson", "Omen", "Trap"}
NON_CREATURE_LAND_SUBTYPES = ARTIFACT_TYPES | ENCHANTMENT_TYPES | SPELL_TYPES

# Land types (CR 205.3i) that can appear alongside creature types on land
# creatures such as Dryad Arbor ("Land Creature — Forest Dryad").
LAND_TYPES = {
    "Cave",
    "Desert",
    "Forest",
    "Gate",
    "Island",
    "Lair",
    "Locus",
    "Mine",
    "Mountain",
    "Plains",
    "Power-Plant",
    "Sphere",
    "Swamp",
    "Tower",
    "Town",
    "Urza's",
}

# Card types whose subtypes include creature types (CR 205.3m, 308.3).
CREATURE_SUBTYPE_CARD_TYPES = {"Creature", "Kindred", "Tribal"}
