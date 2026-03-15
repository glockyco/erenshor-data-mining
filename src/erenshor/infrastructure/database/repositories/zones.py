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
            return [Zone.model_validate(dict(row)) for row in rows]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve zones: {e}") from e

    def get_zone_connections(self, scene_name: str) -> list[str]:
        """Return wiki_page_names of all zones reachable from scene_name via zone_lines.

        Includes both enabled (is_enabled=1) and disabled (is_enabled=0) zone_lines.
        Disabled lines represent quest-gated connections that are still relevant for
        navigation context.

        Excludes:
        - Rows where destination_zone_stable_key IS NULL (one known case: Soluna's Landing).
        - Self-references where the destination's wiki_page_name equals the source.
        - Destinations with NULL wiki_page_name (excluded from wiki).

        Args:
            scene_name: The scene_name column value of the source zone.

        Returns:
            Deduplicated, alphabetically sorted list of wiki_page_name strings.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT DISTINCT z_dst.wiki_page_name
            FROM zone_lines zl
            JOIN zones z_dst
              ON z_dst.stable_key = zl.destination_zone_stable_key
            WHERE zl.scene = ?
              AND zl.destination_zone_stable_key IS NOT NULL
              AND z_dst.wiki_page_name IS NOT NULL
            ORDER BY z_dst.wiki_page_name COLLATE NOCASE
        """
        try:
            rows = self._execute_raw(query, (scene_name,))
            return [str(row["wiki_page_name"]) for row in rows]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve connections for '{scene_name}': {e}") from e
