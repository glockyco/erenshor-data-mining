"""Spawn point repository for specialized spawn queries."""

from typing import Any, cast

from loguru import logger

from erenshor.domain.entities.spawn_point import SpawnPoint
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo, TreasureRole
from erenshor.domain.value_objects.wiki_link import ItemLink, ZoneLink
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

# The zones where a player meets a character on a treasure hunt: a chest at
# the dig sites where it can lie, and a guardian at the sites of the chests
# whose TreasureChestEvent spawns it.
_TREASURE_ZONES = """
    WITH sites AS (
        SELECT tcp.chest_character_stable_key AS character_stable_key,
               tcp.treasure_location_stable_key, 'chest' AS treasure_role
        FROM treasure_chest_possible_spawns tcp
        UNION
        SELECT ccs.child_stable_key, tcp.treasure_location_stable_key, 'guardian'
        FROM character_chained_spawns ccs
        JOIN treasure_chest_possible_spawns tcp ON tcp.chest_character_stable_key = ccs.parent_stable_key
        WHERE ccs.source_script = 'TreasureChestEvent'
    )
    SELECT DISTINCT
        z.stable_key        AS zone_stable_key,
        z.display_name      AS zone_display_name,
        z.wiki_page_name    AS zone_wiki_page_name,
        sites.treasure_role
    FROM sites
    JOIN treasure_locations tl ON tl.stable_key = sites.treasure_location_stable_key
    JOIN zones z ON z.scene_name = tl.scene
    WHERE sites.character_stable_key IN (
        SELECT d.member_stable_key
        FROM character_deduplications d
        WHERE d.group_key = (
            SELECT d2.group_key FROM character_deduplications d2 WHERE d2.member_stable_key = ?
        )
        AND d.is_wiki_generated = 1
    )
    ORDER BY z.stable_key COLLATE NOCASE
"""


def _zone_link(row: Any) -> ZoneLink:
    zone_display = str(row["zone_display_name"]) if row["zone_display_name"] else str(row["zone_stable_key"])
    zone_wiki = str(row["zone_wiki_page_name"]) if row["zone_wiki_page_name"] else None
    return ZoneLink(page_title=zone_wiki, display_name=zone_display, stable_key=str(row["zone_stable_key"]))


def _furniture_link(row: Any) -> ItemLink | None:
    """The furniture set that places a furnishing of the Reliquary's planning table, if any."""
    if row["furniture_stable_key"] is None:
        return None
    return ItemLink(
        page_title=str(row["furniture_wiki_page_name"]) if row["furniture_wiki_page_name"] else None,
        display_name=str(row["furniture_display_name"]),
        image_name=str(row["furniture_image_name"]) if row["furniture_image_name"] else None,
        stable_key=str(row["furniture_stable_key"]),
    )


class SpawnPointRepository(BaseRepository[SpawnPoint]):
    """Repository for spawn-point-specific database queries.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_spawn_info_for_character(self, character_stable_key: str) -> list[CharacterSpawnInfo]:
        """Get all spawn point locations for a character's dedup group.

        Aggregates spawns across ALL members of the character's dedup group,
        not just the representative. This ensures placed instances that were
        deduped into the same group contribute their spawn locations. A
        treasure chest or guardian adds one entry without a position for each
        zone where a treasure hunt can lead to it.

        Args:
            character_stable_key: Character stable key (typically the group representative)

        Returns:
            List of CharacterSpawnInfo objects for all spawn locations.
            Empty list if character has no spawn points.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                cs.zone_stable_key,
                z.display_name      AS zone_display_name,
                z.wiki_page_name    AS zone_wiki_page_name,
                cs.spawn_delay_4    AS base_respawn,
                cs.x,
                cs.y,
                cs.z,
                cs.spawn_chance,
                cs.source_script,
                cs.event_x,
                cs.event_y,
                cs.event_z,
                COALESCE(cs.is_rare, 0)  AS is_rare,
                COALESCE(cs.level_mod, 0) AS level_mod,
                fi.stable_key       AS furniture_stable_key,
                fi.display_name     AS furniture_display_name,
                fi.wiki_page_name   AS furniture_wiki_page_name,
                fi.image_name       AS furniture_image_name
            FROM wiki_character_spawns cs
            JOIN characters c ON c.stable_key = cs.character_stable_key
            LEFT JOIN zones z ON z.stable_key = cs.zone_stable_key
            LEFT JOIN items fi ON fi.stable_key = cs.furniture_item_stable_key
            WHERE cs.character_stable_key IN (
                SELECT d.member_stable_key
                FROM character_deduplications d
                WHERE d.group_key = (
                    SELECT d2.group_key
                    FROM character_deduplications d2
                    WHERE d2.member_stable_key = ?
                )
                AND d.is_wiki_generated = 1
            )
              AND (cs.spawn_chance > 0 OR cs.source_script IS NOT NULL)
              AND cs.zone_stable_key IS NOT NULL
            ORDER BY cs.zone_stable_key COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (character_stable_key,))
            spawn_infos = [
                CharacterSpawnInfo(
                    zone_link=_zone_link(row),
                    base_respawn=float(row["base_respawn"]) if row["base_respawn"] is not None else None,
                    x=float(row["x"]) if row["x"] is not None else None,
                    y=float(row["y"]) if row["y"] is not None else None,
                    z=float(row["z"]) if row["z"] is not None else None,
                    spawn_chance=float(row["spawn_chance"]) if row["spawn_chance"] is not None else None,
                    is_rare=bool(row["is_rare"]),
                    level_mod=int(row["level_mod"]),
                    source_script=(str(row["source_script"]) if row["source_script"] is not None else None),
                    event_x=float(row["event_x"]) if row["event_x"] is not None else None,
                    event_y=float(row["event_y"]) if row["event_y"] is not None else None,
                    event_z=float(row["event_z"]) if row["event_z"] is not None else None,
                    furniture=_furniture_link(row),
                )
                for row in rows
            ]
            spawn_infos.extend(
                CharacterSpawnInfo(
                    zone_link=_zone_link(row),
                    base_respawn=None,
                    x=None,
                    y=None,
                    z=None,
                    spawn_chance=None,
                    is_rare=False,
                    treasure_role=cast("TreasureRole", row["treasure_role"]),
                )
                for row in self._execute_raw(_TREASURE_ZONES, (character_stable_key,))
            )

            logger.debug(f"Retrieved {len(spawn_infos)} spawn point(s) for {character_stable_key}")
            return spawn_infos
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve spawn info for {character_stable_key}: {e}") from e
