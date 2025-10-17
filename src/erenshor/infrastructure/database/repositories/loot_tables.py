"""Loot table repository for database operations."""

from typing import Any

from erenshor.domain.entities.loot_table import LootTable
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake, snake_to_pascal


class LootTableRepository(BaseRepository[LootTable]):
    """Repository for LootTable entities.

    Provides basic CRUD operations for loot drop tables. Custom queries can
    be added as needed using raw SQL via execute_query().

    NOTE: LootTable uses a composite key (character_prefab_guid, item_id),
    so standard get_by_id operations are not meaningful. Use custom queries
    when needed.
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

    # TODO: Add custom query methods as needed using raw SQL
