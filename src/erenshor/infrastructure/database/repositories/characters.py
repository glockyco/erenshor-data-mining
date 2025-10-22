"""Character repository for specialized character queries."""

from erenshor.domain.entities.character import Character
from erenshor.infrastructure.database.repository import BaseRepository


class CharacterRepository(BaseRepository[Character]):
    """Repository for character-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
