"""Zone repository for wiki generation queries."""

from erenshor.domain.entities.zone import Zone
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class ZoneRepository(BaseRepository[Zone]):
    """Repository for zone-specific database queries.

    All queries target the clean snake_case database (built by `extract build`).
    """

    def get_all_zones(self) -> list[Zone]:
        """Return all zones ordered by wiki_page_name.

        Zones without a wiki_page_name (excluded from the wiki) are sorted last.

        Returns:
            List of Zone entities.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                stable_key,
                scene_name,
                zone_name,
                is_dungeon,
                zone_type,
                raid_capable,
                use_zone_as_temp_bind,
                display_name,
                wiki_page_name,
                image_name,
                is_wiki_generated,
                is_map_visible,
                achievement,
                complete_quest_on_enter_stable_key,
                complete_second_quest_on_enter_stable_key,
                assign_quest_on_enter_stable_key,
                north_bearing
            FROM zones
            ORDER BY COALESCE(wiki_page_name, 'zzz') COLLATE NOCASE
        """
        try:
            rows = self._execute_raw(query)
            zones: list[Zone] = []
            for row in rows:
                values = dict(row)
                values["raid_capable"] = bool(values.get("raid_capable"))
                zones.append(Zone.model_validate(values))
            return zones
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve zones: {e}") from e

    def get_zone_connections(self, scene_name: str) -> list[str]:
        """Return fixed destination page titles for lines with physical zoning capability.

        Disabled lines remain available to the legacy page's gate descriptions.
        Stored returns have no fixed destination and are omitted here.

        Args:
            scene_name: The scene_name column value of the source zone.

        Returns:
            Deduplicated, alphabetically sorted list of wiki_page_name strings.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT DISTINCT z_dst.wiki_page_name
            FROM zone_lines_with_zoning_capability zl
            JOIN zones z_dst
              ON z_dst.stable_key = zl.destination_zone_stable_key
            LEFT JOIN zone_line_destination_contexts dc ON dc.zone_line_stable_key = zl.stable_key
            WHERE zl.scene = ?
              AND zl.destination_zone_stable_key IS NOT NULL
              AND z_dst.wiki_page_name IS NOT NULL
              AND dc.zone_line_stable_key IS NULL
            ORDER BY z_dst.wiki_page_name COLLATE NOCASE
        """
        try:
            rows = self._execute_raw(query, (scene_name,))
            return [str(row["wiki_page_name"]) for row in rows]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve connections for '{scene_name}': {e}") from e

    def get_zone_overview_spawns(self) -> list[dict[str, object]]:
        """Return placed character groups with combat capability and NPC level inputs."""
        query = """
            SELECT DISTINCT s.zone_stable_key AS zone,
                   COALESCE(d.group_key, c.stable_key) AS character,
                   c.encounter_tier AS tier, c.can_be_damaged AS damageable,
                   COALESCE(c.is_friendly, 0) AS friendly,
                   c.level, COALESCE(s.level_mod, 0) AS levelMod,
                   COALESCE(c.group_encounter, 0) AS "group",
                   COALESCE(c.level_scales_with_player, 0) AS scales
            FROM wiki_character_spawns s
            JOIN characters c ON c.stable_key = s.character_stable_key
            JOIN zones z ON z.stable_key = s.zone_stable_key AND z.wiki_page_name IS NOT NULL
            LEFT JOIN character_deduplications d ON d.member_stable_key = c.stable_key
            WHERE s.spawn_chance > 0 OR s.source_script IS NOT NULL OR s.is_directly_placed = 1
            ORDER BY zone, character, c.level, levelMod
        """
        try:
            return [dict(row) for row in self._execute_raw(query, ())]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve zone overview spawns: {e}") from e

    def get_zone_overview_connections(self) -> list[dict[str, object]]:
        """Retain conditional fixed exits and stored returns without evaluating player state."""
        query = """
            SELECT src.stable_key AS zone, l.stable_key AS line,
                   CASE WHEN dc.kind IS NULL THEN l.destination_zone_stable_key END AS destination,
                   COALESCE(dc.kind, 'fixed') AS kind,
                   CASE WHEN l.is_enabled = 0 OR EXISTS (
                       SELECT 1 FROM gate_conditions g
                       WHERE g.subject_kind = 'zone_line' AND g.subject_stable_key = l.stable_key
                   ) THEN 1 ELSE 0 END AS conditional
            FROM zone_lines_with_zoning_capability l
            JOIN zones src ON src.scene_name = l.scene AND src.wiki_page_name IS NOT NULL
            LEFT JOIN zone_line_destination_contexts dc ON dc.zone_line_stable_key = l.stable_key
            ORDER BY zone, l.stable_key
        """
        try:
            return [dict(row) for row in self._execute_raw(query, ())]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve zone overview connections: {e}") from e
