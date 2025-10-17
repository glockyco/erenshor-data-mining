"""Faction repository for database operations."""

from typing import Any

from erenshor.domain.entities.faction import Faction
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake, snake_to_pascal


class FactionRepository(BaseRepository[Faction]):
    """Repository for Faction entities.

    Provides type-safe database operations for factions and reputation systems.
    """

    @property
    def table_name(self) -> str:
        """Get the database table name."""
        return "Factions"

    @property
    def id_column(self) -> str:
        """Get the primary key column name."""
        return "REFNAME"

    def _row_to_entity(self, row: Any) -> Faction:
        """Convert database row to Faction entity.

        Args:
            row: Database row with PascalCase column names.

        Returns:
            Faction domain entity with snake_case fields.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            # Convert row to dict with snake_case keys
            # Special handling for REFNAME (all caps)
            data = {}
            for key in row:
                if key == "REFNAME":
                    data["refname"] = row[key]
                else:
                    data[pascal_to_snake(key)] = row[key]
            return Faction(**data)
        except Exception as e:
            raise RepositoryError(f"Failed to convert row to Faction: {e}") from e

    def _entity_to_row(self, entity: Faction) -> dict[str, Any]:
        """Convert Faction entity to database row.

        Args:
            entity: Faction domain entity with snake_case fields.

        Returns:
            Dictionary with PascalCase column names for database.

        Raises:
            RepositoryError: If conversion fails.
        """
        try:
            data = entity.model_dump()
            # Convert to PascalCase, but keep REFNAME all caps
            result = {}
            for key, value in data.items():
                if key == "refname":
                    result["REFNAME"] = value
                else:
                    result[snake_to_pascal(key)] = value
            return result
        except Exception as e:
            raise RepositoryError(f"Failed to convert Faction to row: {e}") from e

    def _get_insert_columns(self) -> list[str]:
        """Get column names for INSERT operations."""
        # Map entity fields to column names
        return ["REFNAME", "ResourceName", "FactionName", "FactionDesc", "DefaultValue"]

    def _get_update_columns(self) -> list[str]:
        """Get column names for UPDATE operations."""
        # Exclude primary key
        return ["ResourceName", "FactionName", "FactionDesc", "DefaultValue"]

    def get_by_refname(self, refname: str) -> Faction | None:
        """Get faction by REFNAME (same as get_by_id since REFNAME is the primary key).

        Args:
            refname: Faction REFNAME.

        Returns:
            Faction if found, None otherwise.
        """
        results = self.execute_query("SELECT * FROM Factions WHERE REFNAME = ?", (refname,))
        return results[0] if results else None
