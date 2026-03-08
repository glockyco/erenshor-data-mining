"""Stance repository for stance-specific queries."""

from loguru import logger

from erenshor.domain.entities.stance import Stance
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


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
            SELECT *
            FROM stances
            ORDER BY display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            stances = [Stance.model_validate(dict(row)) for row in rows]
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
            SELECT *
            FROM stances
            WHERE stable_key = ?
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            if not rows:
                logger.debug(f"Stance not found: {stable_key}")
                return None
            return Stance.model_validate(dict(rows[0]))
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve stance {stable_key}: {e}") from e
