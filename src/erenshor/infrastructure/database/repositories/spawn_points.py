"""Spawn point repository for database operations."""

from typing import Any

from erenshor.domain.entities.spawn_point import SpawnPoint
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake, snake_to_pascal


class SpawnPointRepository(BaseRepository[SpawnPoint]):
    """Repository for SpawnPoint entities.

    Provides basic CRUD operations for creature and NPC spawn points. Custom
    queries can be added as needed using raw SQL via execute_query().

    NOTE: Spawn point characters are stored in the SpawnPointCharacters junction
    table. Use relationship repositories to load these.
    """

    @property
    def table_name(self) -> str:
        """Get the database table name."""
        return "SpawnPoints"

    @property
    def id_column(self) -> str:
        """Get the primary key column name."""
        return "Id"

    def _row_to_entity(self, row: Any) -> SpawnPoint:
        """Convert database row to SpawnPoint entity.

        Args:
            row: Database row with PascalCase column names.

        Returns:
            SpawnPoint domain entity with snake_case fields.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            # Convert row to dict with snake_case keys
            data = {pascal_to_snake(key): row[key] for key in row}
            return SpawnPoint(**data)
        except Exception as e:
            raise RepositoryError(f"Failed to convert row to SpawnPoint: {e}") from e

    def _entity_to_row(self, entity: SpawnPoint) -> dict[str, Any]:
        """Convert SpawnPoint entity to database row.

        Args:
            entity: SpawnPoint domain entity with snake_case fields.

        Returns:
            Dictionary with PascalCase column names for database.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            data = entity.model_dump()
            return {snake_to_pascal(key): value for key, value in data.items()}
        except Exception as e:
            raise RepositoryError(f"Failed to convert SpawnPoint to row: {e}") from e

    def _get_insert_columns(self) -> list[str]:
        """Get column names for INSERT operations."""
        entity_fields = SpawnPoint.model_fields.keys()
        # Id is auto-generated
        columns = [snake_to_pascal(field) for field in entity_fields if field != "id"]
        return columns

    def _get_update_columns(self) -> list[str]:
        """Get column names for UPDATE operations."""
        entity_fields = SpawnPoint.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields if field != "id"]
        return columns

    # TODO: Add custom query methods as needed using raw SQL
