"""Repository pattern for specialized database queries.

DESIGN PHILOSOPHY:
This module provides MINIMAL infrastructure for entity-specific database queries.
We deliberately avoid building a generic CRUD framework - instead, repositories
should contain SPECIALIZED queries for SPECIFIC data needs in the pipeline.

USAGE GUIDELINES:
1. Add query methods ONLY when actually needed for a feature
2. Use raw SQL directly - no query builder abstractions
3. Methods should be specialized for specific use cases, not generic access
4. Follow YAGNI principle - "The best code is code that doesn't have to be written"

EXAMPLES OF GOOD QUERIES (specific, purposeful):
- get_vendor_items() -> items sold by NPCs for wiki vendor tables
- get_spawn_points_for_character(character_id) -> spawn data for character pages
- get_quest_chain(quest_id) -> complete quest chain for wiki quest guides

EXAMPLES OF BAD QUERIES (generic, premature):
- get_by_id() -> use raw SQL when needed instead
- get_all() -> rarely need all entities, query specific subset
- create()/update() -> we're read-only, Unity exports handle writes

When you need database access for a new feature:
1. Write raw SQL query for your specific use case
2. Add it as a focused method in the appropriate repository
3. Document what it's for (which pipeline feature/page type needs it)
"""

from typing import Any, TypeVar

from pydantic import BaseModel

from .connection import DatabaseConnection

# Generic type variable for entity models
T = TypeVar("T", bound=BaseModel)


class RepositoryError(Exception):
    """Raised when repository query operations fail.

    This indicates:
    - Query execution failed
    - Entity conversion failed
    - Database access error
    """

    pass


class BaseRepository[T: BaseModel]:
    """Minimal base class for entity-specific repository implementations.

    This class provides ONLY:
    1. Database connection management
    2. Helper method for executing raw SQL queries
    3. Type safety via generics

    Subclasses should add SPECIALIZED query methods for SPECIFIC features as needed.
    Do NOT add generic CRUD methods - write focused queries for actual use cases.

    Attributes:
        db: DatabaseConnection instance for executing queries.

    Example of a GOOD repository (specialized queries):
        >>> class CharacterRepository(BaseRepository[Character]):
        ...     def get_vendors(self) -> list[Character]:
        ...         '''Get all vendor NPCs for wiki vendor tables.'''
        ...         query = "SELECT * FROM Characters WHERE IsVendor = 1"
        ...         return self._execute_query(query, self._row_to_entity)
        ...
        ...     def get_spawn_data_for_character(self, char_id: int) -> list[SpawnInfo]:
        ...         '''Get spawn points for character page spawn locations section.'''
        ...         query = '''
        ...             SELECT sp.*, c.ZoneId, z.SceneName
        ...             FROM SpawnPoints sp
        ...             JOIN SpawnPointCharacters spc ON sp.Id = spc.SpawnPointId
        ...             JOIN Coordinates c ON sp.CoordinateId = c.Id
        ...             JOIN Zones z ON c.ZoneId = z.Id
        ...             WHERE spc.CharacterId = ?
        ...         '''
        ...         rows = self._execute_raw(query, (char_id,))
        ...         return [self._row_to_spawn_info(row) for row in rows]
    """

    def __init__(self, db: DatabaseConnection) -> None:
        """Initialize repository with database connection.

        Args:
            db: DatabaseConnection instance for database access.
        """
        self.db = db

    def _execute_raw(self, query: str, params: tuple[Any, ...] = ()) -> list[Any]:
        """Execute raw SQL query and return database rows.

        Use this for queries that don't directly map to a single entity type.

        Args:
            query: SQL query string.
            params: Query parameters (tuple).

        Returns:
            List of sqlite3.Row objects.

        Raises:
            RepositoryError: If query execution fails.

        Example:
            >>> rows = self._execute_raw("SELECT * FROM Characters WHERE Level > ?", (50,))
            >>> for row in rows:
            ...     print(row["ObjectName"])
        """
        with self.db.connect() as conn:
            try:
                cursor = conn.execute(query, params)
                return cursor.fetchall()
            except Exception as e:
                raise RepositoryError(f"Query failed: {e}\nQuery: {query}") from e
