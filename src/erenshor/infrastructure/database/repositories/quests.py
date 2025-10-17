"""Quest repository for database operations."""

from typing import Any

from erenshor.domain.entities.quest import Quest
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake, snake_to_pascal


class QuestRepository(BaseRepository[Quest]):
    """Repository for Quest entities.

    Provides type-safe database operations for quests and their objectives,
    requirements, and rewards.

    NOTE: Quest requirements and rewards are stored in junction tables
    (QuestRequiredItems, QuestRewards, etc.). Use relationship repositories
    to load these.
    """

    @property
    def table_name(self) -> str:
        """Get the database table name."""
        return "Quests"

    @property
    def id_column(self) -> str:
        """Get the primary key column name."""
        return "QuestDBIndex"

    def _row_to_entity(self, row: Any) -> Quest:
        """Convert database row to Quest entity.

        Args:
            row: Database row with PascalCase column names.

        Returns:
            Quest domain entity with snake_case fields.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            # Convert row to dict with snake_case keys
            data = {pascal_to_snake(key): row[key] for key in row}
            return Quest(**data)
        except Exception as e:
            raise RepositoryError(f"Failed to convert row to Quest: {e}") from e

    def _entity_to_row(self, entity: Quest) -> dict[str, Any]:
        """Convert Quest entity to database row.

        Args:
            entity: Quest domain entity with snake_case fields.

        Returns:
            Dictionary with PascalCase column names for database.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            data = entity.model_dump()
            return {snake_to_pascal(key): value for key, value in data.items()}
        except Exception as e:
            raise RepositoryError(f"Failed to convert Quest to row: {e}") from e

    def _get_insert_columns(self) -> list[str]:
        """Get column names for INSERT operations."""
        entity_fields = Quest.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields if field != "quest_db_index"]
        return columns

    def _get_update_columns(self) -> list[str]:
        """Get column names for UPDATE operations."""
        entity_fields = Quest.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields if field != "quest_db_index"]
        return columns

    def get_by_db_name(self, db_name: str) -> Quest | None:
        """Get quest by database name (stable identifier).

        Args:
            db_name: Quest database name.

        Returns:
            Quest if found, None otherwise.
        """
        results = self.execute_query("SELECT * FROM Quests WHERE DBName = ?", (db_name,))
        return results[0] if results else None

    def get_repeatable(self) -> list[Quest]:
        """Get all repeatable quests.

        Returns:
            List of repeatable quests.
        """
        return self.execute_query("SELECT * FROM Quests WHERE Repeatable = 1")
