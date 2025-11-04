"""Value objects for faction system."""

from pydantic import BaseModel, Field

__all__ = ["FactionModifier"]


class FactionModifier(BaseModel):
    """Faction relationship modifier for a character.

    Represents the reputation change that occurs when this character is killed.
    Positive values increase reputation (become more friendly), negative values
    decrease reputation (become more hostile).

    Example:
        >>> modifier = FactionModifier(faction_refname="FACTION_GUARDS", modifier_value=-5)
        >>> # Killing this character decreases Guards reputation by 5 points
    """

    faction_refname: str = Field(description="Faction REFNAME (not display name)")
    modifier_value: int = Field(description="Reputation change (+friendly, -hostile)")

    model_config = {"frozen": True}  # Immutable value object
