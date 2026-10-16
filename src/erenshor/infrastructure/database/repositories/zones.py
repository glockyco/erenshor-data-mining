"""Zone repository for wiki generation queries."""

from typing import Any

from erenshor.domain.entities.zone import Zone
from erenshor.domain.value_objects.source_info import ObtainedFromInfo
from erenshor.domain.value_objects.wiki_link import ZoneLink
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


def _zone_link(row: Any) -> ZoneLink:
    """The zone link of a row with the zone's stable key, display name, and page."""
    return ZoneLink(
        page_title=str(row["wiki_page_name"]) if row["wiki_page_name"] else None,
        display_name=str(row["display_name"] or row["stable_key"]),
        stable_key=str(row["stable_key"]),
    )


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

    def get_mining_nodes_for_item(self, item_stable_key: str) -> list[ObtainedFromInfo]:
        """Return mining nodes where an item is found, with node chance."""
        query = """
            SELECT mn.stable_key AS mining_node_stable_key, MAX(mni.drop_chance) AS drop_chance
            FROM mining_node_items mni
            JOIN mining_nodes mn ON mn.stable_key = mni.mining_node_stable_key
            JOIN zones z ON z.scene_name = mn.scene
            WHERE mni.item_stable_key = ?
            GROUP BY mn.stable_key
            ORDER BY mn.stable_key
        """
        try:
            rows = self._execute_raw(query, (item_stable_key,))
            return [
                ObtainedFromInfo(
                    source_type="mining",
                    source_key=str(row["mining_node_stable_key"]),
                    probability=float(row["drop_chance"]) if row["drop_chance"] is not None else None,
                )
                for row in rows
            ]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve mining sources for '{item_stable_key}': {e}") from e

    def get_fishing_waters_for_item(self, item_stable_key: str) -> list[ObtainedFromInfo]:
        """Return fishing waters and day/night chances for an item."""
        query = """
            WITH fish_rows AS (
                SELECT
                    w.stable_key AS water_stable_key,
                    CASE wf.type
                        WHEN 'DayFishable' THEN 'day'
                        WHEN 'NightFishable' THEN 'night'
                        ELSE LOWER(wf.type)
                    END AS source_condition,
                    wf.drop_chance
                FROM water_fishables wf
                JOIN waters w ON w.stable_key = wf.water_stable_key
                JOIN zones z ON z.scene_name = w.scene
                WHERE wf.item_stable_key = ?
            )
            SELECT water_stable_key, source_condition, MAX(drop_chance) AS drop_chance
            FROM fish_rows
            GROUP BY water_stable_key, source_condition
            ORDER BY water_stable_key, source_condition
        """
        try:
            rows = self._execute_raw(query, (item_stable_key,))
            return [
                ObtainedFromInfo(
                    source_type="fishing",
                    source_key=str(row["water_stable_key"]),
                    probability=float(row["drop_chance"]) if row["drop_chance"] is not None else None,
                    condition=str(row["source_condition"]),
                )
                for row in rows
            ]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve fishing sources for '{item_stable_key}': {e}") from e

    def get_item_bag_sources_for_item(self, item_stable_key: str) -> list[ObtainedFromInfo]:
        """Return item bags that contain an item."""
        query = """
            SELECT ib.stable_key AS item_bag_stable_key
            FROM item_bags ib
            JOIN zones z ON z.scene_name = ib.scene
            WHERE ib.item_stable_key = ?
            ORDER BY ib.stable_key
        """
        try:
            rows = self._execute_raw(query, (item_stable_key,))
            return [
                ObtainedFromInfo(source_type="item_bag", source_key=str(row["item_bag_stable_key"])) for row in rows
            ]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve item-bag sources for '{item_stable_key}': {e}") from e

    def get_mining_zones_for_item(self, item_stable_key: str) -> list[tuple[ZoneLink, float]]:
        """Return each zone with a mining node of an item and the node chances there, by zone name.

        The rows are the nodes of ``get_mining_nodes_for_item``; a zone repeats once for each chance.
        """
        query = """
            SELECT DISTINCT z.stable_key, z.display_name, z.wiki_page_name, mni.drop_chance
            FROM mining_node_items mni
            JOIN mining_nodes mn ON mn.stable_key = mni.mining_node_stable_key
            JOIN zones z ON z.scene_name = mn.scene
            WHERE mni.item_stable_key = ? AND mni.drop_chance IS NOT NULL
            ORDER BY z.display_name COLLATE NOCASE, mni.drop_chance
        """
        try:
            rows = self._execute_raw(query, (item_stable_key,))
            return [(_zone_link(row), float(row["drop_chance"])) for row in rows]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve mining zones for '{item_stable_key}': {e}") from e

    def get_fishing_zones_for_item(self, item_stable_key: str) -> list[tuple[ZoneLink, str, float]]:
        """Return each zone with water that yields an item, with the period and chance, by zone name.

        The rows are the waters of ``get_fishing_waters_for_item``; the period is ``day`` or ``night``.
        """
        query = """
            SELECT DISTINCT z.stable_key, z.display_name, z.wiki_page_name,
                CASE wf.type WHEN 'DayFishable' THEN 'day' WHEN 'NightFishable' THEN 'night' ELSE LOWER(wf.type) END
                    AS period,
                wf.drop_chance
            FROM water_fishables wf
            JOIN waters w ON w.stable_key = wf.water_stable_key
            JOIN zones z ON z.scene_name = w.scene
            WHERE wf.item_stable_key = ? AND wf.drop_chance IS NOT NULL
            ORDER BY z.display_name COLLATE NOCASE, period, wf.drop_chance
        """
        try:
            rows = self._execute_raw(query, (item_stable_key,))
            return [(_zone_link(row), str(row["period"]), float(row["drop_chance"])) for row in rows]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve fishing zones for '{item_stable_key}': {e}") from e

    def get_item_bag_zones_for_item(self, item_stable_key: str) -> list[ZoneLink]:
        """Return each zone with an item bag of an item, by zone name: the bags of ``get_item_bag_sources_for_item``."""
        query = """
            SELECT DISTINCT z.stable_key, z.display_name, z.wiki_page_name
            FROM item_bags ib
            JOIN zones z ON z.scene_name = ib.scene
            WHERE ib.item_stable_key = ?
            ORDER BY z.display_name COLLATE NOCASE
        """
        try:
            return [_zone_link(row) for row in self._execute_raw(query, (item_stable_key,))]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve item-bag zones for '{item_stable_key}': {e}") from e
