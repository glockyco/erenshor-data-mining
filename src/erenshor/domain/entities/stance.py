"""Stance entity model.

This module defines the Stance domain entity representing combat stances
that modify character stats when activated by specific skills.
"""

from pydantic import Field

from .base import BaseEntity


class Stance(BaseEntity):
    """Domain entity representing a combat stance.

    Stances are combat modifiers activated by skills that adjust primary
    stats (Strength, Agility, Intelligence) for tactical advantages.
    The StableKey field is used as the stable identifier.

    All fields match the Unity export schema from the Stances table.
    """

    # Primary keys and identifiers
    stable_key: str = Field(description="Stable key from database (primary key)")

    # Display fields
    name: str | None = Field(default=None, description="Display name of the stance")
    icon: str | None = Field(default=None, description="Icon asset name")

    # Stat modifiers (percentage-based)
    strength_modifier: int | None = Field(default=None, description="Strength modifier percentage")
    agility_modifier: int | None = Field(default=None, description="Agility modifier percentage")
    intelligence_modifier: int | None = Field(default=None, description="Intelligence modifier percentage")
