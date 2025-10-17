"""Character repository for database operations."""

from typing import Any

from erenshor.domain.entities.character import Character
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake, snake_to_pascal


class CharacterRepository(BaseRepository[Character]):
    """Repository for Character entities.

    Provides type-safe database operations for NPCs, creatures, vendors,
    and other in-game characters.

    NOTE: Character abilities are stored in junction tables (CharacterAttackSpells,
    CharacterBuffSpells, etc.). Use relationship repositories to load these.
    """

    @property
    def table_name(self) -> str:
        """Get the database table name."""
        return "Characters"

    @property
    def id_column(self) -> str:
        """Get the primary key column name."""
        return "Id"

    def _row_to_entity(self, row: Any) -> Character:
        """Convert database row to Character entity.

        Args:
            row: Database row with PascalCase column names.

        Returns:
            Character domain entity with snake_case fields.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            # Convert row to dict with snake_case keys
            data = {pascal_to_snake(key): row[key] for key in row}
            return Character(**data)
        except Exception as e:
            raise RepositoryError(f"Failed to convert row to Character: {e}") from e

    def _entity_to_row(self, entity: Character) -> dict[str, Any]:
        """Convert Character entity to database row.

        Args:
            entity: Character domain entity with snake_case fields.

        Returns:
            Dictionary with PascalCase column names for database.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            data = entity.model_dump()
            return {snake_to_pascal(key): value for key, value in data.items()}
        except Exception as e:
            raise RepositoryError(f"Failed to convert Character to row: {e}") from e

    def _get_insert_columns(self) -> list[str]:
        """Get column names for INSERT operations."""
        entity_fields = Character.model_fields.keys()
        # Id is auto-generated
        columns = [snake_to_pascal(field) for field in entity_fields if field != "id"]
        return columns

    def _get_update_columns(self) -> list[str]:
        """Get column names for UPDATE operations."""
        entity_fields = Character.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields if field != "id"]
        return columns

    def get_by_object_name(self, object_name: str) -> Character | None:
        """Get character by object name.

        Args:
            object_name: Character object name (stable identifier).

        Returns:
            Character if found, None otherwise.
        """
        results = self.execute_query("SELECT * FROM Characters WHERE ObjectName = ?", (object_name,))
        return results[0] if results else None

    def get_by_faction(self, faction: str) -> list[Character]:
        """Get characters by faction.

        Args:
            faction: Faction name.

        Returns:
            List of characters in the specified faction.
        """
        return self.execute_query("SELECT * FROM Characters WHERE MyFaction = ?", (faction,))

    def get_vendors(self) -> list[Character]:
        """Get all vendor characters.

        Returns:
            List of vendor characters.
        """
        return self.execute_query("SELECT * FROM Characters WHERE IsVendor = 1")

    def get_by_level_range(self, min_level: int, max_level: int) -> list[Character]:
        """Get characters within a level range.

        Args:
            min_level: Minimum level (inclusive).
            max_level: Maximum level (inclusive).

        Returns:
            List of characters within the level range.
        """
        return self.execute_query(
            "SELECT * FROM Characters WHERE Level >= ? AND Level <= ?",
            (min_level, max_level),
        )
