"""Spawn point repository for specialized spawn queries."""

from erenshor.domain.entities.spawn_point import SpawnPoint
from erenshor.infrastructure.database.repository import BaseRepository


class SpawnPointRepository(BaseRepository[SpawnPoint]):
    """Repository for spawn-point-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
