"""Loot table repository for database operations."""

from typing import Any

from erenshor.domain.entities.loot_table import LootTable
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake, snake_to_pascal


class LootTableRepository(BaseRepository[LootTable]):
    """Repository for LootTable entities.

    Provides type-safe database operations for loot drop tables.

    NOTE: LootTable uses a composite key (character_prefab_guid, item_id),
    so standard get_by_id operations are not meaningful. Use custom queries
    or get_by_composite_key instead.
    """

    @property
    def table_name(self) -> str:
        """Get the database table name."""
        return "LootDrops"

    @property
    def id_column(self) -> str:
        """Get the primary key column name.

        NOTE: LootDrops doesn't have a single ID column. We use CharacterPrefabGuid
        as a placeholder, but prefer using custom queries.
        """
        return "CharacterPrefabGuid"

    def _row_to_entity(self, row: Any) -> LootTable:
        """Convert database row to LootTable entity.

        Args:
            row: Database row with PascalCase column names.

        Returns:
            LootTable domain entity with snake_case fields.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            # Convert row to dict with snake_case keys
            data = {pascal_to_snake(key): row[key] for key in row}
            return LootTable(**data)
        except Exception as e:
            raise RepositoryError(f"Failed to convert row to LootTable: {e}") from e

    def _entity_to_row(self, entity: LootTable) -> dict[str, Any]:
        """Convert LootTable entity to database row.

        Args:
            entity: LootTable domain entity with snake_case fields.

        Returns:
            Dictionary with PascalCase column names for database.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            data = entity.model_dump()
            return {snake_to_pascal(key): value for key, value in data.items()}
        except Exception as e:
            raise RepositoryError(f"Failed to convert LootTable to row: {e}") from e

    def _get_insert_columns(self) -> list[str]:
        """Get column names for INSERT operations."""
        entity_fields = LootTable.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields]
        return columns

    def _get_update_columns(self) -> list[str]:
        """Get column names for UPDATE operations."""
        # Exclude composite key columns from updates
        entity_fields = LootTable.model_fields.keys()
        columns = [
            snake_to_pascal(field) for field in entity_fields if field not in ("character_prefab_guid", "item_id")
        ]
        return columns

    def get_by_character_guid(self, character_guid: str) -> list[LootTable]:
        """Get all loot drops for a character.

        Args:
            character_guid: Character GUID.

        Returns:
            List of loot table entries for the character.
        """
        return self.execute_query("SELECT * FROM LootDrops WHERE CharacterPrefabGuid = ?", (character_guid,))

    def get_by_item_id(self, item_id: str) -> list[LootTable]:
        """Get all characters that drop a specific item.

        Args:
            item_id: Item ID.

        Returns:
            List of loot table entries for the item.
        """
        return self.execute_query("SELECT * FROM LootDrops WHERE ItemId = ?", (item_id,))

    def get_by_composite_key(self, character_guid: str, item_id: str) -> LootTable | None:
        """Get loot table entry by composite key.

        Args:
            character_guid: Character GUID.
            item_id: Item ID.

        Returns:
            LootTable entry if found, None otherwise.
        """
        results = self.execute_query(
            "SELECT * FROM LootDrops WHERE CharacterPrefabGuid = ? AND ItemId = ?",
            (character_guid, item_id),
        )
        return results[0] if results else None

    def get_guaranteed_drops(self) -> list[LootTable]:
        """Get all guaranteed drop entries.

        Returns:
            List of guaranteed loot drops.
        """
        return self.execute_query("SELECT * FROM LootDrops WHERE IsGuaranteed = 1")
