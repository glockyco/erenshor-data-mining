"""Spawn point repository for specialized spawn queries."""

from loguru import logger

from erenshor.domain.entities.spawn_point import SpawnPoint
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
from erenshor.domain.value_objects.wiki_link import ZoneLink
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class SpawnPointRepository(BaseRepository[SpawnPoint]):
    """Repository for spawn-point-specific database queries.

    All queries should use raw SQL via self._execute_raw().
    """

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
                COALESCE(cs.is_rare, 0)  AS is_rare,
                COALESCE(c.is_unique, 0) AS is_unique,
                COALESCE(cs.level_mod, 0) AS level_mod
            FROM character_spawns cs
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
            )
              AND COALESCE(cs.spawn_chance, 0) > 0
              AND cs.zone_stable_key IS NOT NULL
              AND COALESCE(cs.is_enabled, 1) = 1
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
                zone_link = ZoneLink(page_title=zone_wiki, display_name=zone_display)
                spawn_infos.append(
                    CharacterSpawnInfo(
                        zone_link=zone_link,
                        base_respawn=float(row["base_respawn"]) if row["base_respawn"] is not None else None,
                        x=float(row["x"]) if row["x"] is not None else None,
                        y=float(row["y"]) if row["y"] is not None else None,
                        z=float(row["z"]) if row["z"] is not None else None,
                        spawn_chance=float(row["spawn_chance"]),
                        is_rare=bool(row["is_rare"]),
                        is_unique=bool(row["is_unique"]),
                        level_mod=int(row["level_mod"]),
                    )
                )

            logger.debug(f"Retrieved {len(spawn_infos)} spawn point(s) for {character_stable_key}")
            return spawn_infos
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve spawn info for {character_stable_key}: {e}") from e
