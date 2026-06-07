"""Loot table repository for specialized loot queries."""

from loguru import logger

from erenshor.domain.entities.loot_table import LootTable
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class LootTableRepository(BaseRepository[LootTable]):
    """Repository for loot-table-specific database queries.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_loot_for_character(self, character_stable_key: str) -> list[LootDropInfo]:
        """Get all drops for a character as pure drop-edge data.

        Each `LootDropInfo` carries the dropped item's StableKey plus the drop's own
        facts (probability, guaranteed-pool membership, visible-equipped). The item's
        page, name, and uniqueness are resolved from the item record at the display
        layer, never duplicated here. Only drops whose item exists with a display name
        are returned.

        Args:
            character_stable_key: Character stable key

        Returns:
            List of LootDropInfo objects, sorted by drop probability (descending),
            then item display name. Empty list if the character has no loot.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                ld.item_stable_key,
                ld.drop_probability,
                ld.is_guaranteed,
                ld.is_visible
            FROM loot_drops ld
            JOIN items i ON i.stable_key = ld.item_stable_key
            WHERE ld.character_stable_key = ?
              AND i.display_name IS NOT NULL
            ORDER BY ld.drop_probability DESC, i.display_name COLLATE NOCASE, ld.item_stable_key
        """

        try:
            rows = self._execute_raw(query, (character_stable_key,))

            loot_drops = [
                LootDropInfo(
                    item_stable_key=str(row["item_stable_key"]),
                    drop_probability=float(row["drop_probability"]),
                    is_guaranteed=bool(row["is_guaranteed"]),
                    is_visible=bool(row["is_visible"]),
                )
                for row in rows
            ]

            logger.debug(f"Retrieved {len(loot_drops)} loot drops for character {character_stable_key}")
            return loot_drops
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve loot for character {character_stable_key}: {e}") from e
