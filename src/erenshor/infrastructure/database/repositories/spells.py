"""Spell repository for specialized spell queries."""

from erenshor.domain.entities.spell import Spell
from erenshor.infrastructure.database.repository import BaseRepository


class SpellRepository(BaseRepository[Spell]):
    """Repository for spell-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
