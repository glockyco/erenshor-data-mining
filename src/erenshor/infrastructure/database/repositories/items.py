"""Item repository for database operations."""

from typing import Any

from erenshor.domain.entities.item import Item
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake, snake_to_pascal


class ItemRepository(BaseRepository[Item]):
    """Repository for Item entities.

    Provides type-safe database operations for items including equipment,
    consumables, quest items, and crafting materials.
    """

    @property
    def table_name(self) -> str:
        """Get the database table name."""
        return "Items"

    @property
    def id_column(self) -> str:
        """Get the primary key column name."""
        return "Id"

    def _row_to_entity(self, row: Any) -> Item:
        """Convert database row to Item entity.

        Args:
            row: Database row with PascalCase column names.

        Returns:
            Item domain entity with snake_case fields.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            # Convert row to dict with snake_case keys
            data = {pascal_to_snake(key): row[key] for key in row}
            return Item(**data)
        except Exception as e:
            raise RepositoryError(f"Failed to convert row to Item: {e}") from e

    def _entity_to_row(self, entity: Item) -> dict[str, Any]:
        """Convert Item entity to database row.

        Args:
            entity: Item domain entity with snake_case fields.

        Returns:
            Dictionary with PascalCase column names for database.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            # Get entity data and convert snake_case to PascalCase
            data = entity.model_dump()
            return {snake_to_pascal(key): value for key, value in data.items()}
        except Exception as e:
            raise RepositoryError(f"Failed to convert Item to row: {e}") from e

    def _get_insert_columns(self) -> list[str]:
        """Get column names for INSERT operations.

        ItemDBIndex is auto-generated, so we exclude it from inserts.
        """
        # Get all fields from entity and convert to PascalCase, excluding auto-generated
        entity_fields = Item.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields if field != "item_db_index"]
        return columns

    def _get_update_columns(self) -> list[str]:
        """Get column names for UPDATE operations.

        Exclude primary key (Id) from updates.
        """
        # Get all fields except the primary key
        entity_fields = Item.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields if field not in ("id", "item_db_index")]
        return columns

    def get_by_resource_name(self, resource_name: str) -> Item | None:
        """Get item by resource name.

        Args:
            resource_name: Item resource name.

        Returns:
            Item if found, None otherwise.
        """
        results = self.execute_query("SELECT * FROM Items WHERE ResourceName = ?", (resource_name,))
        return results[0] if results else None
