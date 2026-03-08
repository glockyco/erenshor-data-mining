"""Faction repository for specialized faction queries."""

from loguru import logger

from erenshor.domain.entities.faction import Faction
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class FactionRepository(BaseRepository[Faction]):
    """Repository for faction-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_by_stable_key(self, stable_key: str) -> Faction | None:
        """Get a faction by its stable key.

        Used to build faction wiki links by looking up display_name and
        wiki_page_name for a given faction stable key.

        Args:
            stable_key: Faction stable key (e.g., "faction:Fernalla")

        Returns:
            Faction entity if found, None otherwise.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT *
            FROM factions
            WHERE stable_key = ?
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            if not rows:
                logger.debug(f"Faction not found: {stable_key}")
                return None
            return Faction.model_validate(dict(rows[0]))
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve faction {stable_key}: {e}") from e
