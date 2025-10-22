"""Quest repository for specialized quest queries."""

from erenshor.domain.entities.quest import Quest
from erenshor.infrastructure.database.repository import BaseRepository


class QuestRepository(BaseRepository[Quest]):
    """Repository for quest-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
