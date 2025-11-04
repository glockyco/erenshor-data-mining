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

    def get_faction_display_names(self, refnames: list[str]) -> dict[str, str]:
        """Get faction display names (FactionDesc) for given REFNAMEs.

        Used for translating internal faction names to user-facing display names.

        Args:
            refnames: List of faction REFNAMEs (e.g., ["AzureCitizens", "Priel"])

        Returns:
            Dict mapping REFNAME to FactionDesc display name.
            Missing REFNAMEs are not included in the result.

        Raises:
            RepositoryError: If query execution fails.

        Example:
            >>> repo.get_faction_display_names(["AzureCitizens", "Priel"])
            {'AzureCitizens': 'The Citizens of Port Azure', 'Priel': 'Savannah Priel'}
        """
        if not refnames:
            return {}

        # Build query with placeholders for IN clause
        placeholders = ",".join("?" * len(refnames))
        query = f"""
            SELECT
                REFNAME,
                FactionDesc
            FROM Factions
            WHERE REFNAME IN ({placeholders})
        """

        try:
            rows = self._execute_raw(query, tuple(refnames))
            result = {row["REFNAME"]: row["FactionDesc"] for row in rows}
            logger.debug(f"Retrieved display names for {len(result)}/{len(refnames)} factions")
            return result
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve faction display names: {e}") from e
