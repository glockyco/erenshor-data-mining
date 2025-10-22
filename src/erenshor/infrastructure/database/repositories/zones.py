"""Zone repository for specialized zone queries."""

from erenshor.domain.entities.zone import Zone
from erenshor.infrastructure.database.repository import BaseRepository


class ZoneRepository(BaseRepository[Zone]):
    """Repository for zone-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
