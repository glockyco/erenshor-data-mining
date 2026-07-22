"""Spawn point repository for specialized spawn queries."""

from loguru import logger

from erenshor.domain.entities.spawn_point import SpawnPoint
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo, CharacterSpawnRow
from erenshor.domain.value_objects.wiki_link import ZoneLink
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class SpawnPointRepository(BaseRepository[SpawnPoint]):
    """Repository for spawn-point-specific database queries.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_cargo_spawn_rows_for_character(self, character_stable_key: str) -> list[CharacterSpawnRow]:
        """Get complete generated spawn rows, including treasure chest locations."""
        query = """
            WITH grp AS (
                SELECT group_key FROM character_deduplications WHERE member_stable_key = ? LIMIT 1
            ), members AS (
                SELECT member_stable_key
                FROM character_deduplications
                WHERE group_key = (SELECT group_key FROM grp) AND is_wiki_generated = 1
            )
            SELECT DISTINCT
                cs.character_stable_key AS character_key,
                cs.zone_stable_key AS zone,
                cs.scene,
                cs.x, cs.y, cs.z,
                cs.spawn_chance,
                cs.night_spawn,
                cs.spawn_upon_quest_complete_stable_key AS spawn_upon_quest_complete,
                cs.level_mod,
                cs.rare_npc_chance,
                CASE
                    WHEN cs.source_script IS NOT NULL THEN 'dynamic'
                    WHEN cs.is_trigger_spawn = 1 THEN 'trigger'
                    WHEN cs.is_directly_placed = 1 THEN 'direct'
                    ELSE 'normal'
                END AS spawn_type,
                cs.source_script,
                cs.event_x,
                cs.event_y,
                cs.event_z
            FROM wiki_character_spawns cs
            WHERE cs.character_stable_key IN (SELECT member_stable_key FROM members)
            UNION ALL
            SELECT
                tcp.chest_character_stable_key,
                z.stable_key,
                tl.scene,
                tl.x, tl.y, tl.z,
                NULL, NULL, NULL, NULL, NULL,
                'treasure_chest',
                NULL, NULL, NULL, NULL
            FROM treasure_chest_possible_spawns tcp
            JOIN treasure_locations tl ON tl.stable_key = tcp.treasure_location_stable_key
            LEFT JOIN zones z ON z.scene_name = tl.scene
            WHERE tcp.chest_character_stable_key = ?
            ORDER BY character_key, scene, x, y, z, spawn_type
        """
        try:
            rows = self._execute_raw(query, (character_stable_key, character_stable_key))
            return [
                CharacterSpawnRow(
                    character_key=str(row["character_key"]),
                    zone=str(row["zone"]) if row["zone"] is not None else None,
                    scene=str(row["scene"]) if row["scene"] is not None else None,
                    x=float(row["x"]) if row["x"] is not None else None,
                    y=float(row["y"]) if row["y"] is not None else None,
                    z=float(row["z"]) if row["z"] is not None else None,
                    spawn_chance=float(row["spawn_chance"]) if row["spawn_chance"] is not None else None,
                    night_spawn=bool(row["night_spawn"]) if row["night_spawn"] is not None else None,
                    spawn_upon_quest_complete=(
                        str(row["spawn_upon_quest_complete"]) if row["spawn_upon_quest_complete"] is not None else None
                    ),
                    level_mod=int(row["level_mod"]) if row["level_mod"] is not None else None,
                    rare_npc_chance=int(row["rare_npc_chance"]) if row["rare_npc_chance"] is not None else None,
                    spawn_type=str(row["spawn_type"]),
                    event_x=float(row["event_x"]) if row["event_x"] is not None else None,
                    event_y=float(row["event_y"]) if row["event_y"] is not None else None,
                    event_z=float(row["event_z"]) if row["event_z"] is not None else None,
                    origin=("dynamic" if row["source_script"] is not None else "generated"),
                )
                for row in rows
            ]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve Cargo spawn rows for '{character_stable_key}': {e}") from e

    def get_spawn_info_for_character(self, character_stable_key: str) -> list[CharacterSpawnInfo]:
        """Get all spawn point locations for a character's dedup group.

        Aggregates spawns across ALL members of the character's dedup group,
        not just the representative. This ensures placed instances that were
        deduped into the same group contribute their spawn locations.

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
                COALESCE(c.is_unique, 0) AS is_unique,
                COALESCE(cs.level_mod, 0) AS level_mod
            FROM wiki_character_spawns cs
            JOIN characters c ON c.stable_key = cs.character_stable_key
            LEFT JOIN zones z ON z.stable_key = cs.zone_stable_key
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

            if not rows:
                return []

            spawn_infos = []
            for row in rows:
                zone_display = (
                    str(row["zone_display_name"]) if row["zone_display_name"] else str(row["zone_stable_key"])
                )
                zone_wiki = str(row["zone_wiki_page_name"]) if row["zone_wiki_page_name"] else None
                zone_link = ZoneLink(
                    page_title=zone_wiki,
                    display_name=zone_display,
                    stable_key=str(row["zone_stable_key"]),
                )
                spawn_infos.append(
                    CharacterSpawnInfo(
                        zone_link=zone_link,
                        base_respawn=float(row["base_respawn"]) if row["base_respawn"] is not None else None,
                        x=float(row["x"]) if row["x"] is not None else None,
                        y=float(row["y"]) if row["y"] is not None else None,
                        z=float(row["z"]) if row["z"] is not None else None,
                        spawn_chance=float(row["spawn_chance"]) if row["spawn_chance"] is not None else None,
                        is_rare=bool(row["is_rare"]),
                        is_unique=bool(row["is_unique"]),
                        level_mod=int(row["level_mod"]),
                        source_script=(str(row["source_script"]) if row["source_script"] is not None else None),
                        event_x=float(row["event_x"]) if row["event_x"] is not None else None,
                        event_y=float(row["event_y"]) if row["event_y"] is not None else None,
                        event_z=float(row["event_z"]) if row["event_z"] is not None else None,
                    )
                )

            logger.debug(f"Retrieved {len(spawn_infos)} spawn point(s) for {character_stable_key}")
            return spawn_infos
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve spawn info for {character_stable_key}: {e}") from e
