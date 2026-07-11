"""Value objects for spawn system."""

from dataclasses import dataclass

from erenshor.domain.value_objects.wiki_link import ZoneLink

__all__ = ["CharacterSpawnInfo", "CharacterSpawnRow"]


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
    spawn_chance: float | None
    is_rare: bool
    is_unique: bool
    level_mod: int = 0
    source_script: str | None = None


@dataclass(frozen=True)
class CharacterSpawnRow:
    """Complete generated spawn row stored in the character-owned Cargo table."""

    character_key: str
    zone: str | None
    scene: str | None
    x: float | None
    y: float | None
    z: float | None
    spawn_chance: float | None
    night_spawn: bool | None
    spawn_upon_quest_complete: str | None
    level_mod: int | None
    rare_npc_chance: int | None
    spawn_type: str
    origin: str = "generated"
