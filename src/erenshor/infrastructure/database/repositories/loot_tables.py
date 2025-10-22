"""Loot table repository for specialized loot queries."""

from erenshor.domain.entities.loot_table import LootTable
from erenshor.infrastructure.database.repository import BaseRepository


class LootTableRepository(BaseRepository[LootTable]):
    """Repository for loot-table-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
