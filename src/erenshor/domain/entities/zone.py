"""Zone entity model.

Zones are geographic areas in the game world, defined by the Zones table in the clean
database. ZoneLines define connections between zones.
"""

from pydantic import Field

from .base import BaseEntity


class Zone(BaseEntity):
    """Domain entity representing an in-game zone.

    Maps to the zones table in the clean database (built by extract build).
    wiki_page_name is populated by the build pipeline's mapping system and may
    be None for zones excluded from the wiki.

    Boolean columns from SQLite are stored as integers (0/1) to match strict
    Pydantic validation — do not change to bool.
    """

    # Primary key
    stable_key: str = Field(description="Stable key: 'zone:{scene_name}'")

    # Zone identification
    scene_name: str = Field(description="Unity scene name; doubles as interactive map key")
    zone_name: str = Field(description="Raw display name from game data")
    is_dungeon: int = Field(description="1 for dungeon zones, 0 for outdoor/event zones")

    # Build-pipeline mapping fields
    display_name: str = Field(description="Display name (may be overridden by mapping)")
    wiki_page_name: str | None = Field(default=None, description="Canonical wiki page title; None = excluded")
    image_name: str = Field(description="Image filename for wiki pages")
    is_wiki_generated: int = Field(description="1 if auto-generated wiki content exists")
    is_map_visible: int = Field(description="1 if zone appears on the interactive map")

    # Quest triggers
    achievement: str = Field(default="", description="Achievement identifier on zone entry")
    complete_quest_on_enter_stable_key: str | None = Field(default=None, description="Quest completed on zone entry")
    complete_second_quest_on_enter_stable_key: str | None = Field(
        default=None, description="Second quest completed on zone entry"
    )
    assign_quest_on_enter_stable_key: str | None = Field(default=None, description="Quest assigned on zone entry")

    # Navigation
    north_bearing: float = Field(default=0.0, description="Compass north bearing in degrees")
