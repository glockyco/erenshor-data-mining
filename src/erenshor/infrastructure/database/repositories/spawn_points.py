"""Spawn point repository for specialized spawn queries.

Add query methods here ONLY when actually needed for specific features.

GOOD examples (when to add queries):
- get_character_spawns(character_id) -> for wiki character location sections
- get_zone_spawns(zone_id) -> for wiki zone spawn tables
- get_rare_spawns() -> for wiki rare spawn lists
- get_patrol_routes(spawn_id) -> for wiki patrol path sections

BAD examples (do not add):
- get_by_id() -> use raw SQL when needed
- get_all() -> too broad, query specific subset
- create()/update() -> we're read-only
"""

from erenshor.domain.entities.spawn_point import SpawnPoint
from erenshor.infrastructure.database.repository import BaseRepository


class SpawnPointRepository(BaseRepository[SpawnPoint]):
    """Repository for spawn-point-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
