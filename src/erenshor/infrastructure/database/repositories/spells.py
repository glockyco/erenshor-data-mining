"""Spell repository for database operations."""

from typing import Any

from erenshor.domain.entities.spell import Spell
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake, snake_to_pascal


class SpellRepository(BaseRepository[Spell]):
    """Repository for Spell entities.

    Provides basic CRUD operations for spells including damage spells, buffs,
    debuffs, heals, and crowd control effects. Custom queries can be added as
    needed using raw SQL via execute_query().
    """

    @property
    def table_name(self) -> str:
        """Get the database table name."""
        return "Spells"

    @property
    def id_column(self) -> str:
        """Get the primary key column name."""
        return "SpellDBIndex"

    def _row_to_entity(self, row: Any) -> Spell:
        """Convert database row to Spell entity.

        Args:
            row: Database row with PascalCase column names.

        Returns:
            Spell domain entity with snake_case fields.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            # Convert row to dict with snake_case keys
            # Handle aliases: Str→strength, Dex→dexterity, etc.
            data = {}
            for key in row:
                snake_key = pascal_to_snake(key)
                # Map abbreviated stat names to full names
                if snake_key in ("str", "dex", "end", "agi", "wis", "int", "cha", "mr", "er", "pr", "vr"):
                    # Skip - these will be handled by Pydantic aliases
                    continue
                data[snake_key] = row[key]

            return Spell(**data)
        except Exception as e:
            raise RepositoryError(f"Failed to convert row to Spell: {e}") from e

    def _entity_to_row(self, entity: Spell) -> dict[str, Any]:
        """Convert Spell entity to database row.

        Args:
            entity: Spell domain entity with snake_case fields.

        Returns:
            Dictionary with PascalCase column names for database.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            # Get entity data with aliases (uses abbreviated names)
            data = entity.model_dump(by_alias=True)
            return {snake_to_pascal(key): value for key, value in data.items()}
        except Exception as e:
            raise RepositoryError(f"Failed to convert Spell to row: {e}") from e

    def _get_insert_columns(self) -> list[str]:
        """Get column names for INSERT operations.

        SpellDBIndex is auto-generated, so we exclude it from inserts.
        """
        # Get all fields and convert to PascalCase with aliases
        entity_fields = Spell.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields if field != "spell_db_index"]
        return columns

    def _get_update_columns(self) -> list[str]:
        """Get column names for UPDATE operations.

        Exclude primary key (SpellDBIndex) from updates.
        """
        entity_fields = Spell.model_fields.keys()
        columns = [snake_to_pascal(field) for field in entity_fields if field != "spell_db_index"]
        return columns

    # TODO: Add custom query methods as needed using raw SQL
