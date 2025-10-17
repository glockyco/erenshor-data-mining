"""Skill repository for database operations."""

from typing import Any

from erenshor.domain.entities.skill import Skill
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake, snake_to_pascal


class SkillRepository(BaseRepository[Skill]):
    """Repository for Skill entities.

    Provides basic CRUD operations for combat skills and special abilities.
    Custom queries can be added as needed using raw SQL via execute_query().
    """

    @property
    def table_name(self) -> str:
        """Get the database table name."""
        return "Skills"

    @property
    def id_column(self) -> str:
        """Get the primary key column name."""
        return "SkillDBIndex"

    def _row_to_entity(self, row: Any) -> Skill:
        """Convert database row to Skill entity.

        Args:
            row: Database row with PascalCase column names.

        Returns:
            Skill domain entity with snake_case fields.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            # Convert row to dict with snake_case keys
            data = {pascal_to_snake(key): row[key] for key in row}
            return Skill(**data)
        except Exception as e:
            raise RepositoryError(f"Failed to convert row to Skill: {e}") from e

    def _entity_to_row(self, entity: Skill) -> dict[str, Any]:
        """Convert Skill entity to database row.

        Args:
            entity: Skill domain entity with snake_case fields.

        Returns:
            Dictionary with PascalCase column names for database.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            data = entity.model_dump()
            return {snake_to_pascal(key): value for key, value in data.items()}
        except Exception as e:
            raise RepositoryError(f"Failed to convert Skill to row: {e}") from e

    def _get_insert_columns(self) -> list[str]:
        """Get column names for INSERT operations."""
        entity_fields = Skill.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields if field != "skill_db_index"]
        return columns

    def _get_update_columns(self) -> list[str]:
        """Get column names for UPDATE operations."""
        entity_fields = Skill.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields if field != "skill_db_index"]
        return columns

    # TODO: Add custom query methods as needed using raw SQL
