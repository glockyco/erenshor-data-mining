"""Value objects for faction system."""

from pydantic import BaseModel, Field

__all__ = ["FactionModifier"]


class FactionModifier(BaseModel):
    """Faction relationship modifier for a character.

    Represents the reputation change that occurs when this character is killed.
    Positive values increase reputation (become more friendly), negative values
    decrease reputation (become more hostile).

    Example:
        >>> modifier = FactionModifier(faction_stable_key="faction:guards", modifier_value=-5)
        >>> # Killing this character decreases Guards reputation by 5 points
    """

    faction_stable_key: str = Field(description="Faction stable key (format: 'faction:resource_name')")
    modifier_value: int = Field(description="Reputation change (+friendly, -hostile)")

    model_config = {"frozen": True}  # Immutable value object
