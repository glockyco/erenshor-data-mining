"""Zone entity model.

This module defines the Zone domain entity representing in-game zones, areas,
and map locations. Zones are represented by the Coordinates table with
scene/location information.
"""

from pydantic import Field

from erenshor.registry.resource_names import build_stable_key, normalize_resource_name
from erenshor.registry.schema import EntityType

from .base import BaseEntity


class Zone(BaseEntity):
    """Domain entity representing an in-game zone or map location.

    Zones are geographic areas in the game world. They are tracked through
    the Coordinates table which stores scene names and spatial positions.

    This entity uses the Scene field as the stable identifier for zones.
    """

    # Primary key
    id: int = Field(description="Database ID (primary key)")

    # Zone identification
    scene: str | None = Field(default=None, description="Scene/zone name")

    # Spatial coordinates
    x: float | None = Field(default=None, description="X coordinate")
    y: float | None = Field(default=None, description="Y coordinate")
    z: float | None = Field(default=None, description="Z coordinate")

    # Coordinate category
    category: str | None = Field(default=None, description="Coordinate category/type")

    # Entity references (foreign keys to other tables)
    achievement_trigger_id: int | None = Field(default=None, description="Achievement trigger reference")
    character_id: int | None = Field(default=None, description="Character reference")
    door_id: int | None = Field(default=None, description="Door reference")
    mining_node_id: int | None = Field(default=None, description="Mining node reference")
    secret_passage_id: int | None = Field(default=None, description="Secret passage reference")
    spawn_point_id: int | None = Field(default=None, description="Spawn point reference")
    teleport_id: int | None = Field(default=None, description="Teleport reference")
    treasure_loc_id: int | None = Field(default=None, description="Treasure location reference")
    water_id: int | None = Field(default=None, description="Water reference")
    zone_line_id: int | None = Field(default=None, description="Zone line reference")
    item_bag_id: int | None = Field(default=None, description="Item bag reference")

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
