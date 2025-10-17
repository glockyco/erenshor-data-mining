"""Item repository for specialized item queries.

Add query methods here ONLY when actually needed for specific features.

GOOD examples (when to add queries):
- get_vendor_items(vendor_id) -> for wiki vendor tables
- get_craftable_items() -> for wiki crafting guides
- get_quest_rewards() -> for wiki quest reward sections
- get_item_stats_by_quality(item_id) -> for wiki item stat tables

BAD examples (do not add):
- get_by_id() -> use raw SQL when needed
- get_all() -> too broad, query specific subset
- create()/update() -> we're read-only
"""

from erenshor.domain.entities.item import Item
from erenshor.infrastructure.database.repository import BaseRepository


class ItemRepository(BaseRepository[Item]):
    """Repository for item-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
