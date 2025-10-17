"""Faction repository for specialized faction queries.

Add query methods here ONLY when actually needed for specific features.

GOOD examples (when to add queries):
- get_faction_members(faction_id) -> for wiki faction member lists
- get_faction_reputation_changes() -> for wiki reputation tables
- get_hostile_factions(faction_id) -> for wiki faction relationship sections

BAD examples (do not add):
- get_by_id() -> use raw SQL when needed
- get_all() -> too broad, query specific subset
- create()/update() -> we're read-only
"""

from erenshor.domain.entities.faction import Faction
from erenshor.infrastructure.database.repository import BaseRepository


class FactionRepository(BaseRepository[Faction]):
    """Repository for faction-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
