"""Value objects for faction system."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["FactionModifier"]


@dataclass(frozen=True)
class FactionModifier:
    """Faction relationship modifier for a character.

    Attributes:
        faction_name: Name of the faction being modified
        modifier_value: Numeric modifier to faction standing (positive = friendly, negative = hostile)
    """

    faction_name: str
    modifier_value: int
