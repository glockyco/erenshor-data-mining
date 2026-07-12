"""Game mechanics constants for Erenshor.

These constants represent game engine values used in calculations.
"""

__all__ = [
    "COORDINATE_PRECISION",
    "DROP_PROBABILITY_PRECISION",
    "GAME_TICKS_PER_SECOND",
    "INFOBOX_IMAGE_SIZE",
    "INSTANT_CAST_THRESHOLD",
    "LONG_NAME_FONT_SIZE",
    "LONG_NAME_THRESHOLD",
    "REQUIRED_TIER_COUNT",
    "SECONDS_PER_DURATION_TICK",
    "TIER_ORDER_MAP",
    "TIER_SORT_DEFAULT",
    "TIER_STRING_MAP",
    "WEAPON_DELAY_PRECISION",
    "WIKITEXT_LINE_SEPARATOR",
]

# Tick rates
GAME_TICKS_PER_SECOND = 60
"""Game engine runs at 60 ticks per second.

Skills.Cooldown is stored in ticks and must be divided by this value
to convert to seconds for display.
"""

SECONDS_PER_DURATION_TICK = 3
"""Duration ticks represent 3-second intervals.

Spells.SpellDurationInTicks uses this interval. Multiply by this value
to get duration in seconds. The game runs TickEffects() every 180 frames
(180 / 60 FPS = 3 seconds), where StatusEffect.Duration is decremented by 1.
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
REQUIRED_TIER_COUNT = 8
"""Required number of exported quality tiers for weapons and armor."""

TIER_SORT_DEFAULT = 99
"""Default sort value for unknown tier qualities."""

TIER_ORDER_MAP: dict[str, int] = {
    "Normal": 0,
    "Improved +1": 1,
    "Improved +2": 2,
    "Improved +3": 3,
    "Improved +4": 4,
    "Improved +5": 5,
    "Blessed": 6,
    "Ascended": 7,
}
"""Mapping of quality names to gameplay progression order.

Runtime quality IDs are not a power ranking.  Improved qualities progress
before Blessed and Ascended even though their runtime IDs are 11--15.
"""

# Visual tiers are intentionally separate from progression order.  The legacy
# templates use these values for color/sparkle styling.
TIER_STRING_MAP: dict[str, str] = {
    "Normal": "0",
    "Blessed": "1",
    "Ascended": "2",
    "Improved +1": "3",
    "Improved +2": "4",
    "Improved +3": "5",
    "Improved +4": "6",
    "Improved +5": "7",
}
"""Mapping of quality names to legacy visual tier values."""

# Wikitext formatting constants
WIKITEXT_LINE_SEPARATOR = "<br>"
"""HTML line break tag used to separate lines in wikitext fields."""
