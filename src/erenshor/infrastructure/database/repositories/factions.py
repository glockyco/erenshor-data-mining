"""Faction repository for specialized faction queries."""

from erenshor.domain.entities.faction import Faction
from erenshor.infrastructure.database.repository import BaseRepository


class FactionRepository(BaseRepository[Faction]):
    """Repository for faction-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
