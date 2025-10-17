"""Zone repository for specialized zone queries.

Add query methods here ONLY when actually needed for specific features.

GOOD examples (when to add queries):
- get_zone_connections(zone_id) -> for wiki zone connection maps
- get_zone_npcs(zone_id) -> for wiki zone NPC lists
- get_zone_spawn_points(zone_id) -> for wiki zone spawn tables

BAD examples (do not add):
- get_by_id() -> use raw SQL when needed
- get_all() -> too broad, query specific subset
- create()/update() -> we're read-only
"""

from erenshor.domain.entities.zone import Zone
from erenshor.infrastructure.database.repository import BaseRepository


class ZoneRepository(BaseRepository[Zone]):
    """Repository for zone-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
