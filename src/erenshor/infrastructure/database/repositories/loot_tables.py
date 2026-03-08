"""Loot table repository for specialized loot queries."""

from loguru import logger

from erenshor.domain.entities.loot_table import LootTable
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.domain.value_objects.wiki_link import ItemLink
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class LootTableRepository(BaseRepository[LootTable]):
    """Repository for loot-table-specific database queries.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_loot_for_character(self, character_stable_key: str) -> list[LootDropInfo]:
        """Get all loot drops for a character.

        Returns loot information including item links, drop probabilities, and rarity flags.
        Filters out placeholder/aggregate entries that don't resolve to concrete items.
        The item_link on each result is pre-built from the items JOIN — section generators
        call str(drop.item_link) directly.

        Args:
            character_stable_key: Character stable key

        Returns:
            List of LootDropInfo objects for all loot drops.
            Empty list if character has no loot.
            Sorted by drop probability (descending), then item display name.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                ld.drop_probability,
                ld.is_guaranteed,
                COALESCE(ld.is_actual, 0)     AS is_actual,
                ld.is_common,
                ld.is_uncommon,
                ld.is_rare,
                ld.is_legendary,
                ld.is_visible,
                COALESCE(ld.is_unique, 0)     AS is_unique,
                i.display_name                AS item_display_name,
                i.wiki_page_name              AS item_wiki_page_name,
                i.image_name                  AS item_image_name,
                ld.item_stable_key,
                COALESCE(i.is_unique, 0)      AS item_unique
            FROM loot_drops ld
            LEFT JOIN items i ON i.stable_key = ld.item_stable_key
            WHERE ld.character_stable_key = ?
            ORDER BY ld.drop_probability DESC, i.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (character_stable_key,))

            loot_drops = []
            for row in rows:
                # Skip if item display name is None (unresolved/excluded item)
                if row["item_display_name"] is None:
                    logger.debug(
                        f"Skipping loot entry with no display name for item_stable_key: {row['item_stable_key']}"
                    )
                    continue

                item_link = ItemLink(
                    page_title=str(row["item_wiki_page_name"]) if row["item_wiki_page_name"] else None,
                    display_name=str(row["item_display_name"]),
                    image_name=str(row["item_image_name"]) if row["item_image_name"] else None,
                )
                loot_drops.append(
                    LootDropInfo(
                        item_link=item_link,
                        drop_probability=float(row["drop_probability"]),
                        is_guaranteed=bool(row["is_guaranteed"]),
                        is_actual=bool(row["is_actual"]),
                        is_common=bool(row["is_common"]),
                        is_uncommon=bool(row["is_uncommon"]),
                        is_rare=bool(row["is_rare"]),
                        is_legendary=bool(row["is_legendary"]),
                        is_unique=bool(row["is_unique"]),
                        is_visible=bool(row["is_visible"]),
                        item_unique=bool(row["item_unique"]),
                    )
                )

            logger.debug(f"Retrieved {len(loot_drops)} loot drops for character {character_stable_key}")
            return loot_drops
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve loot for character {character_stable_key}: {e}") from e
