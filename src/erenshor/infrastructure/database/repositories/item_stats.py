"""Item stats repository for database operations."""

from typing import Any

from erenshor.domain.entities.item_stats import ItemStats
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake, snake_to_pascal


class ItemStatsRepository(BaseRepository[ItemStats]):
    """Repository for ItemStats entities.

    Provides type-safe database operations for item statistics by quality level.

    NOTE: ItemStats uses a composite key (item_id, quality), so standard
    get_by_id operations are not meaningful. Use custom queries or
    get_by_composite_key instead.
    """

    @property
    def table_name(self) -> str:
        """Get the database table name."""
        return "ItemStats"

    @property
    def id_column(self) -> str:
        """Get the primary key column name.

        NOTE: ItemStats doesn't have a single ID column. We use ItemId
        as a placeholder, but prefer using custom queries.
        """
        return "ItemId"

    def _row_to_entity(self, row: Any) -> ItemStats:
        """Convert database row to ItemStats entity.

        Args:
            row: Database row with PascalCase column names.

        Returns:
            ItemStats domain entity with snake_case fields.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            # Convert row to dict with snake_case keys
            # Handle aliases: HP, AC, Str, Dex, etc.
            data = {}
            for key in row:
                snake_key = pascal_to_snake(key)
                # Keep abbreviated stat names as-is (they match aliases)
                data[snake_key] = row[key]

            return ItemStats(**data)
        except Exception as e:
            raise RepositoryError(f"Failed to convert row to ItemStats: {e}") from e

    def _entity_to_row(self, entity: ItemStats) -> dict[str, Any]:
        """Convert ItemStats entity to database row.

        Args:
            entity: ItemStats domain entity with snake_case fields.

        Returns:
            Dictionary with PascalCase column names for database.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            # Get entity data with aliases (uses abbreviated names like HP, AC, Str)
            data = entity.model_dump(by_alias=True)
            return {snake_to_pascal(key): value for key, value in data.items()}
        except Exception as e:
            raise RepositoryError(f"Failed to convert ItemStats to row: {e}") from e

    def _get_insert_columns(self) -> list[str]:
        """Get column names for INSERT operations."""
        entity_fields = ItemStats.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields]
        return columns

    def _get_update_columns(self) -> list[str]:
        """Get column names for UPDATE operations."""
        # Exclude composite key columns from updates
        entity_fields = ItemStats.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields if field not in ("item_id", "quality")]
        return columns

    def get_by_item_id(self, item_id: str) -> list[ItemStats]:
        """Get all stat variations for an item.

        Args:
            item_id: Item ID.

        Returns:
            List of stat entries for all quality levels.
        """
        return self.execute_query("SELECT * FROM ItemStats WHERE ItemId = ?", (item_id,))

    def get_by_composite_key(self, item_id: str, quality: str) -> ItemStats | None:
        """Get item stats by composite key.

        Args:
            item_id: Item ID.
            quality: Quality level (Normal, Blessed, Godly).

        Returns:
            ItemStats entry if found, None otherwise.
        """
        results = self.execute_query(
            "SELECT * FROM ItemStats WHERE ItemId = ? AND Quality = ?",
            (item_id, quality),
        )
        return results[0] if results else None

    def get_by_quality(self, quality: str) -> list[ItemStats]:
        """Get all item stats for a specific quality level.

        Args:
            quality: Quality level (Normal, Blessed, Godly).

        Returns:
            List of item stats at the specified quality.
        """
        return self.execute_query("SELECT * FROM ItemStats WHERE Quality = ?", (quality,))
