"""Game mechanics constants for Erenshor.

These constants represent game engine values used in calculations.
"""

__all__ = [
    "GAME_TICKS_PER_SECOND",
    "SECONDS_PER_DURATION_TICK",
    "COORDINATE_PRECISION",
    "DROP_PROBABILITY_PRECISION",
    "INFOBOX_IMAGE_SIZE",
    "LONG_NAME_THRESHOLD",
    "LONG_NAME_FONT_SIZE",
    "WEAPON_DELAY_PRECISION",
    "INSTANT_CAST_THRESHOLD",
    "REQUIRED_TIER_COUNT",
    "TIER_SORT_DEFAULT",
    "TIER_ORDER_MAP",
    "TIER_STRING_MAP",
    "WIKITEXT_LINE_SEPARATOR",
]

# Tick rates
GAME_TICKS_PER_SECOND = 60
"""Game engine runs at 60 ticks per second.

Skills.Cooldown is stored in ticks and must be divided by this value
to convert to seconds for display.
"""

SECONDS_PER_DURATION_TICK = 6
"""Duration ticks represent 6-second intervals.

Spells.SpellDurationInTicks uses this interval. Multiply by this value
to get duration in seconds.
"""

# Display formatting constants
COORDINATE_PRECISION = 2
"""Decimal places for X/Y/Z coordinates in location displays."""

DROP_PROBABILITY_PRECISION = 1
"""Decimal places for drop percentages in loot tables."""

WEAPON_DELAY_PRECISION = 1
"""Decimal places for weapon delay values."""

# Image constants
INFOBOX_IMAGE_SIZE = 80
"""Image width in pixels for infobox and fancy table images."""

# Name display constants
LONG_NAME_THRESHOLD = 24
"""Character count threshold for item names to be considered "long"."""

LONG_NAME_FONT_SIZE = "20px"
"""Font size for long item names in fancy tables."""

# Spell/ability constants
INSTANT_CAST_THRESHOLD = 0.05
"""Cast time (in seconds) below which spells are considered instant cast."""

# Tier constants
REQUIRED_TIER_COUNT = 3
"""Required number of tiers for weapons and armor (Normal, Blessed, Godly)."""

TIER_SORT_DEFAULT = 99
"""Default sort value for unknown tier qualities."""

TIER_ORDER_MAP: dict[str, int] = {"Normal": 0, "Blessed": 1, "Godly": 2}
"""Mapping of tier quality names to sort order."""

TIER_STRING_MAP: dict[str, str] = {"Normal": "0", "Blessed": "1", "Godly": "2"}
"""Mapping of tier quality names to tier string values."""

# Wikitext formatting constants
WIKITEXT_LINE_SEPARATOR = "<br>"
"""HTML line break tag used to separate lines in wikitext fields."""
