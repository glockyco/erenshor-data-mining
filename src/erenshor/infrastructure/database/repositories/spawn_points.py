"""Spawn point repository for specialized spawn queries."""

from loguru import logger

from erenshor.domain.entities.spawn_point import SpawnPoint
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class SpawnPointRepository(BaseRepository[SpawnPoint]):
    """Repository for spawn-point-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_spawn_info_for_character(
        self, character_guid: str | None, character_id: int, is_prefab: bool
    ) -> list[CharacterSpawnInfo]:
        """Get all spawn point locations for a character.

        Returns spawn information including coordinates, zone names, respawn times,
        and spawn chances.

        Characters connect to coordinates in two ways:
        - Prefabs: via SpawnPoints and SpawnPointCharacters (can have multiple spawns)
        - Non-prefabs: directly via Coordinates.CharacterId (single location)

        Args:
            character_guid: Character GUID (for prefabs, None for non-prefabs)
            character_id: Character database ID (for non-prefabs)
            is_prefab: True if character is a prefab, False otherwise

        Returns:
            List of CharacterSpawnInfo objects for all spawn locations.
            Empty list if character has no spawn points or coordinates.

        Raises:
            RepositoryError: If query execution fails.

        Example:
            >>> # Prefab character (e.g., wolf - spawns in multiple locations)
            >>> repo.get_spawn_info_for_character("abc123guid", 42, True)
            [CharacterSpawnInfo(...), CharacterSpawnInfo(...)]

            >>> # Non-prefab character (e.g., unique NPC - one fixed location)
            >>> repo.get_spawn_info_for_character(None, 123, False)
            [CharacterSpawnInfo(...)]
        """
        if is_prefab and character_guid:
            # Prefab characters: via spawn points
            return self._get_prefab_spawn_info(character_guid)
        else:
            # Non-prefab characters: direct coordinates
            return self._get_non_prefab_spawn_info(character_id)

    def _get_prefab_spawn_info(self, character_guid: str) -> list[CharacterSpawnInfo]:
        """Get spawn info for prefab characters (via SpawnPoints).

        Prefab characters (IsPrefab=1) can spawn at multiple locations defined
        by SpawnPointCharacters junction table.

        Unique characters (IsUnique=1) have a single spawn point with exact coordinates.
        Non-unique characters have multiple spawn points - we return zone info only,
        deduplicated by zone (no exact coordinates for common spawns).
        """
        query = """
            SELECT
                co.Scene AS scene,
                COALESCE(za.ZoneName, co.Scene) AS zone_display,
                sp.SpawnDelay1 AS base_respawn,
                co.X AS x,
                co.Y AS y,
                co.Z AS z,
                spc.SpawnChance AS spawn_chance,
                COALESCE(spc.IsRare, 0) AS is_rare,
                COALESCE(c.IsUnique, 0) AS is_unique
            FROM SpawnPoints sp
            JOIN SpawnPointCharacters spc ON spc.SpawnPointId = sp.Id
            JOIN Coordinates co ON co.SpawnPointId = sp.Id
            JOIN Characters c ON c.Guid = spc.CharacterGuid
            LEFT JOIN ZoneAnnounces za ON za.SceneName = co.Scene
            WHERE spc.CharacterGuid = ?
              AND COALESCE(spc.SpawnChance, 0) > 0
              AND co.Scene IS NOT NULL
            ORDER BY co.Scene COLLATE NOCASE, co.X, co.Y, co.Z
        """

        try:
            rows = self._execute_raw(query, (character_guid,))

            if not rows:
                return []

            # Check if this is a unique character (single spawn point)
            is_unique = bool(rows[0]["is_unique"])

            if is_unique:
                # Unique characters: should only have one spawn point, include coordinates
                spawn_infos = [CharacterSpawnInfo.model_validate(dict(row)) for row in rows]
                logger.debug(f"Retrieved {len(spawn_infos)} spawn point(s) for unique prefab {character_guid}")
            else:
                # Non-unique characters: deduplicate by zone, omit coordinates
                seen_zones = set()
                spawn_infos = []
                for row in rows:
                    zone = row["scene"]
                    if zone not in seen_zones:
                        seen_zones.add(zone)
                        # Create spawn info without coordinates (zone only)
                        spawn_data = dict(row)
                        spawn_data["x"] = None
                        spawn_data["y"] = None
                        spawn_data["z"] = None
                        spawn_infos.append(CharacterSpawnInfo.model_validate(spawn_data))

                logger.debug(
                    f"Retrieved {len(spawn_infos)} unique zones for non-unique prefab {character_guid} "
                    f"(from {len(rows)} total spawn points)"
                )

            return spawn_infos
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve spawn info for prefab {character_guid}: {e}") from e

    def _get_non_prefab_spawn_info(self, character_id: int) -> list[CharacterSpawnInfo]:
        """Get spawn info for non-prefab characters (direct Coordinates).

        Non-prefab characters (IsPrefab=0) typically have a single fixed location
        stored directly in Coordinates.CharacterId.
        """
        query = """
            SELECT
                co.Scene AS scene,
                COALESCE(za.ZoneName, co.Scene) AS zone_display,
                0.0 AS base_respawn,
                co.X AS x,
                co.Y AS y,
                co.Z AS z,
                100.0 AS spawn_chance,
                0 AS is_rare,
                COALESCE(c.IsUnique, 0) AS is_unique
            FROM Coordinates co
            JOIN Characters c ON c.Id = co.CharacterId
            LEFT JOIN ZoneAnnounces za ON za.SceneName = co.Scene
            WHERE co.CharacterId = ?
              AND co.Scene IS NOT NULL
            ORDER BY co.Scene COLLATE NOCASE, co.X, co.Y, co.Z
        """

        try:
            rows = self._execute_raw(query, (character_id,))
            spawn_infos = [CharacterSpawnInfo.model_validate(dict(row)) for row in rows]
            logger.debug(f"Retrieved {len(spawn_infos)} coordinates for non-prefab character {character_id}")
            return spawn_infos
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve coordinates for non-prefab {character_id}: {e}") from e
