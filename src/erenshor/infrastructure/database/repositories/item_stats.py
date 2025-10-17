"""Item stats repository for specialized item stats queries.

Add query methods here ONLY when actually needed for specific features.

GOOD examples (when to add queries):
- get_item_quality_stats(item_id) -> for wiki item quality tables
- get_stat_scaling_info(item_id) -> for wiki stat scaling sections
- get_quality_variations(item_id) -> for wiki quality comparison tables

BAD examples (do not add):
- get_by_id() -> use raw SQL when needed
- get_all() -> too broad, query specific subset
- create()/update() -> we're read-only
"""

from erenshor.domain.entities.item_stats import ItemStats
from erenshor.infrastructure.database.repository import BaseRepository


class ItemStatsRepository(BaseRepository[ItemStats]):
    """Repository for item-stats-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
