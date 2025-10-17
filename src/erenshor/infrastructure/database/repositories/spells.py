"""Spell repository for database operations."""

from typing import Any

from erenshor.domain.entities.spell import Spell
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake, snake_to_pascal


class SpellRepository(BaseRepository[Spell]):
    """Repository for Spell entities.

    Provides type-safe database operations for spells including damage spells,
    buffs, debuffs, heals, and crowd control effects.
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

    def get_by_resource_name(self, resource_name: str) -> Spell | None:
        """Get spell by resource name.

        Args:
            resource_name: Spell resource name.

        Returns:
            Spell if found, None otherwise.
        """
        results = self.execute_query("SELECT * FROM Spells WHERE ResourceName = ?", (resource_name,))
        return results[0] if results else None

    def get_by_type(self, spell_type: str) -> list[Spell]:
        """Get spells by type.

        Args:
            spell_type: Spell type (e.g., "Damage", "Heal", "Buff").

        Returns:
            List of spells of the specified type.
        """
        return self.execute_query("SELECT * FROM Spells WHERE Type = ?", (spell_type,))
