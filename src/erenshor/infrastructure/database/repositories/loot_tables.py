"""Loot table repository for specialized loot queries."""

from loguru import logger

from erenshor.domain.entities.loot_table import LootTable
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class LootTableRepository(BaseRepository[LootTable]):
    """Repository for loot-table-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_loot_for_character(self, character_guid: str) -> list[LootDropInfo]:
        """Get all loot drops for a character.

        Returns loot information including item names, drop probabilities, and rarity flags.
        Filters out placeholder/aggregate entries that don't resolve to concrete items.

        Args:
            character_guid: Character prefab GUID

        Returns:
            List of LootDropInfo objects for all loot drops.
            Empty list if character has no loot.
            Sorted by drop probability (descending), then item name.

        Raises:
            RepositoryError: If query execution fails.

        Example:
            >>> repo.get_loot_for_character("abc123guid")
            [LootDropInfo(item_name="Gold Coin", drop_probability=95.5, ...)]
        """
        query = """
            SELECT
                ld.DropProbability AS drop_probability,
                ld.IsGuaranteed AS is_guaranteed,
                COALESCE(ld.IsActual, 0) AS is_actual,
                ld.IsCommon AS is_common,
                ld.IsUncommon AS is_uncommon,
                ld.IsRare AS is_rare,
                ld.IsLegendary AS is_legendary,
                ld.IsVisible AS is_visible,
                COALESCE(ld.IsUnique, 0) AS is_unique,
                i.ItemName AS item_name,
                ld.ItemResourceName AS resource_name,
                COALESCE(i."Unique", 0) AS item_unique
            FROM LootDrops ld
            LEFT JOIN Items i ON i.ResourceName = ld.ItemResourceName
            WHERE ld.CharacterPrefabGuid = ?
            ORDER BY ld.DropProbability DESC, i.ItemName COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (character_guid,))

            # Filter out placeholder/aggregate entries that don't resolve to concrete items
            loot_drops = []
            for row in rows:
                row_dict = dict(row)
                # Skip if ItemName is None (placeholder/aggregate entry)
                if row_dict.get("item_name") is None:
                    logger.debug(f"Skipping placeholder loot entry for resource_name: {row_dict.get('resource_name')}")
                    continue

                loot_drops.append(LootDropInfo.model_validate(row_dict))

            logger.debug(f"Retrieved {len(loot_drops)} loot drops for character {character_guid}")
            return loot_drops
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve loot for character {character_guid}: {e}") from e
