"""Stance repository for stance-specific queries."""

from loguru import logger

from erenshor.domain.entities.stance import Stance
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake


class StanceRepository(BaseRepository[Stance]):
    """Repository for stance-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_all(self) -> list[Stance]:
        """Get all stances for wiki page generation.

        Returns all stances with all fields populated.

        Used by: Stance page generators and skill enrichers.

        Returns:
            List of Stance entities.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                StableKey,
                Name,
                Icon,
                StrengthModifier,
                AgilityModifier,
                IntelligenceModifier
            FROM Stances
            ORDER BY Name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            stances = [self._row_to_stance(row) for row in rows]
            logger.debug(f"Retrieved {len(stances)} stances")
            return stances
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve stances: {e}") from e

    def get_by_stable_key(self, stable_key: str) -> Stance | None:
        """Get a stance by its stable key.

        Args:
            stable_key: Stance stable key (e.g., "stance:Aggressive")

        Returns:
            Stance entity if found, None otherwise.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                StableKey,
                Name,
                Icon,
                StrengthModifier,
                AgilityModifier,
                IntelligenceModifier
            FROM Stances
            WHERE StableKey = ?
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            if not rows:
                logger.debug(f"Stance not found: {stable_key}")
                return None
            return self._row_to_stance(rows[0])
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve stance {stable_key}: {e}") from e

    def _row_to_stance(self, row: dict[str, object]) -> Stance:
        """Convert database row to Stance entity.

        Args:
            row: sqlite3.Row object with Stance columns.

        Returns:
            Stance domain entity.
        """
        # Convert row to dict and transform PascalCase keys to snake_case
        data = {pascal_to_snake(key): value for key, value in dict(row).items()}

        # Pydantic will handle validation and type conversion
        return Stance.model_validate(data)
