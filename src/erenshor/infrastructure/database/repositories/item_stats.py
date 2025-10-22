"""Item stats repository for specialized item stats queries."""

from erenshor.domain.entities.item_stats import ItemStats
from erenshor.infrastructure.database.repository import BaseRepository


class ItemStatsRepository(BaseRepository[ItemStats]):
    """Repository for item-stats-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
