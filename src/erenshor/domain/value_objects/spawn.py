"""Value objects for spawn system."""

from pydantic import BaseModel, Field

__all__ = ["CharacterSpawnInfo"]


class CharacterSpawnInfo(BaseModel):
    """Spawn point information for a character.

    Represents one spawn point location where a character can appear.
    Characters can have multiple spawn points.

    Example:
        >>> spawn = CharacterSpawnInfo(
        ...     zone_stable_key="zone:azure",
        ...     base_respawn=120.0,
        ...     x=10.5,
        ...     y=5.2,
        ...     z=100.3,
        ...     spawn_chance=100.0,
        ...     is_rare=False,
        ...     is_unique=False
        ... )
    """

    zone_stable_key: str = Field(description="Zone stable key (format: 'zone:scene_name')")
    base_respawn: float | None = Field(
        default=None,
        description="Respawn time in seconds for 5-player group (NULL for directly-placed NPCs)",
    )
    x: float | None = Field(default=None, description="X coordinate")
    y: float | None = Field(default=None, description="Y coordinate")
    z: float | None = Field(default=None, description="Z coordinate")
    spawn_chance: float = Field(description="Spawn chance percentage (0-100)")
    is_rare: bool = Field(description="Is rare spawn")
    is_unique: bool = Field(description="Is unique/boss spawn")
    level_mod: int = Field(default=0, description="Level modifier applied at spawn")

    model_config = {"frozen": True}  # Immutable value object
