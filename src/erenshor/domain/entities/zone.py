"""Zone entity model.

This module defines the Zone domain entity representing in-game zones and areas.

Zones are defined by Zones and ZoneAtlasEntries tables. The Coordinates
table (which this entity originally represented) contains spatial positions for
various game entities but does not define zones themselves. ZoneLines show
connections between zones.

Note: This entity may need refactoring to properly represent actual zones
rather than coordinates. Currently it stores minimal zone identification data.
"""

from pydantic import Field

from .base import BaseEntity


class Zone(BaseEntity):
    """Domain entity representing an in-game zone or area.

    Zones are geographic areas/regions in the game world. They are properly
    defined by Zones (zone metadata) and ZoneAtlasEntries (map data).
    ZoneLines define connections between zones.

    This entity currently uses the Scene field as the stable identifier.
    """

    # Primary key
    stable_key: str = Field(description="Stable key from database (primary key)")

    # Zone identification
    scene: str | None = Field(default=None, description="Scene/zone name")

    # Zone metadata references
    zone_atlas_entry_id: str | None = Field(default=None, description="Reference to ZoneAtlasEntries.Id")
    zone_announce_id: str | None = Field(default=None, description="Reference to Zones.SceneName")

    # Zone quest triggers
    complete_quest_on_enter_stable_key: str | None = Field(default=None, description="Quest completed on zone entry")
    complete_second_quest_on_enter_stable_key: str | None = Field(
        default=None, description="Second quest completed on zone entry"
    )
    assign_quest_on_enter_stable_key: str | None = Field(default=None, description="Quest assigned on zone entry")
