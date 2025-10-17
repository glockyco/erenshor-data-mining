"""Faction entity model.

This module defines the Faction domain entity representing in-game factions
and reputation systems.
"""

from pydantic import Field

from erenshor.registry.resource_names import build_stable_key, normalize_resource_name
from erenshor.registry.schema import EntityType

from .base import BaseEntity


class Faction(BaseEntity):
    """Domain entity representing an in-game faction.

    Factions represent groups, guilds, or organizations with which players can
    gain or lose reputation. The REFNAME field is used as the stable identifier.

    All fields match the Unity export schema from the Factions table.
    """

    # Primary keys and identifiers
    faction_db_index: int | None = Field(default=None, description="Database index")
    refname: str = Field(description="Stable faction identifier (primary key)")
    resource_name: str | None = Field(default=None, description="Resource name")

    # Display fields
    faction_name: str | None = Field(default=None, description="Display name")
    faction_desc: str | None = Field(default=None, description="Faction description")

    # Reputation
    default_value: float | None = Field(default=None, description="Starting reputation value")

    @property
    def stable_key(self) -> str:
        """Generate stable key for registry lookups.

        Returns:
            Stable key in format "faction:refname"
        """
        return build_stable_key(EntityType.FACTION, self.refname)

    @property
    def normalized_resource_name(self) -> str:
        """Get normalized resource name for comparisons.

        Returns:
            Lowercase, whitespace-normalized refname
        """
        return normalize_resource_name(self.refname)
