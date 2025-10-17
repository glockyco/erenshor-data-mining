"""Zone entity model.

This module defines the Zone domain entity representing in-game zones and areas.

Zones are defined by ZoneAnnounces and ZoneAtlasEntries tables. The Coordinates
table (which this entity originally represented) contains spatial positions for
various game entities but does not define zones themselves. ZoneLines show
connections between zones.

Note: This entity may need refactoring to properly represent actual zones
rather than coordinates. Currently it stores minimal zone identification data.
"""

from pydantic import Field

from erenshor.registry.resource_names import build_stable_key, normalize_resource_name
from erenshor.registry.schema import EntityType

from .base import BaseEntity


class Zone(BaseEntity):
    """Domain entity representing an in-game zone or area.

    Zones are geographic areas/regions in the game world. They are properly
    defined by ZoneAnnounces (zone metadata) and ZoneAtlasEntries (map data).
    ZoneLines define connections between zones.

    This entity currently uses the Scene field as the stable identifier.
    """

    # Primary key
    id: int = Field(description="Database ID (primary key)")

    # Zone identification
    scene: str | None = Field(default=None, description="Scene/zone name")

    # Zone metadata references
    zone_atlas_entry_id: str | None = Field(default=None, description="Reference to ZoneAtlasEntries.Id")
    zone_announce_id: str | None = Field(default=None, description="Reference to ZoneAnnounces.SceneName")

    @property
    def stable_key(self) -> str:
        """Generate stable key for registry lookups.

        Returns:
            Stable key in format "location:scene"

        Raises:
            ValueError: If scene is None
        """
        if self.scene is None:
            raise ValueError("Cannot generate stable_key: scene is None")
        return build_stable_key(EntityType.LOCATION, self.scene)

    @property
    def normalized_resource_name(self) -> str:
        """Get normalized resource name for comparisons.

        Returns:
            Lowercase, whitespace-normalized scene name

        Raises:
            ValueError: If scene is None
        """
        if self.scene is None:
            raise ValueError("Cannot normalize: scene is None")
        return normalize_resource_name(self.scene)
