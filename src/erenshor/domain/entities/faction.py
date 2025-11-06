"""Faction entity model.

This module defines the Faction domain entity representing in-game factions
and reputation systems.
"""

from pydantic import Field

from .base import BaseEntity


class Faction(BaseEntity):
    """Domain entity representing an in-game faction.

    Factions represent reputation groups (NOT guilds). In-game displays
    typically show the faction description rather than the faction name.
    The REFNAME field is used as the stable identifier.

    All fields match the Unity export schema from the Factions table.
    """

    # Primary keys and identifiers
    stable_key: str | None = Field(default=None, description="Stable key from database (primary key)")

    # Display fields
    faction_name: str | None = Field(default=None, description="Display name")
    faction_desc: str | None = Field(default=None, description="Faction description")

    # Reputation
    default_value: float | None = Field(default=None, description="Starting reputation value")
