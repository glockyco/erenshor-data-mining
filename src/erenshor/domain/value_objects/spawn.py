"""Value objects for spawn system."""

from dataclasses import dataclass

from erenshor.domain.value_objects.wiki_link import ZoneLink

__all__ = ["CharacterSpawnInfo"]


@dataclass(frozen=True)
class CharacterSpawnInfo:
    """Spawn point information for a character.

    Represents one spawn point location where a character can appear.
    Characters can have multiple spawn points.

    The zone_link is a pre-built ZoneLink constructed by the repository
    from JOIN columns. Section generators call str(zone_link) to render it.
    """

    zone_link: ZoneLink
    base_respawn: float | None
    x: float | None
    y: float | None
    z: float | None
    spawn_chance: float
    is_rare: bool
    is_unique: bool
    level_mod: int = 0
