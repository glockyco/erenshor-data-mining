"""Value objects for spawn system."""

from dataclasses import dataclass
from typing import Literal

from erenshor.domain.value_objects.wiki_link import ItemLink, ZoneLink

__all__ = ["CharacterSpawnInfo", "TreasureRole"]

# How a character appears on a treasure hunt: as the chest dug up at a site,
# or as a guardian that striking that chest spawns.
TreasureRole = Literal["chest", "guardian"]


@dataclass(frozen=True)
class CharacterSpawnInfo:
    """Spawn point information for a character.

    Represents one spawn point location where a character can appear.
    Characters can have multiple spawn points.

    The zone_link is a pre-built ZoneLink constructed by the repository
    from JOIN columns. Section generators call str(zone_link) to render it.

    A treasure hunt site has a treasure_role and no position: the character
    can appear in the zone at any of several dig sites. A furnishing of the
    Reliquary's planning table names the furniture set that places it.
    """

    zone_link: ZoneLink
    base_respawn: float | None
    x: float | None
    y: float | None
    z: float | None
    spawn_chance: float | None
    is_rare: bool
    level_mod: int = 0
    source_script: str | None = None
    event_x: float | None = None
    event_y: float | None = None
    event_z: float | None = None
    treasure_role: TreasureRole | None = None
    furniture: ItemLink | None = None
