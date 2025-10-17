"""Base repository pattern for type-safe database access.

This module provides the generic base repository pattern for database operations,
implementing CRUD operations with type safety using Python generics.

Features:
- Generic type-safe repository base class
- CRUD operations (create, read, update, delete)
- Bulk operations (insert_many, update_many)
- Query support (integration point for query builders)
- Abstract methods for subclass implementation
- Transaction-aware operations

The BaseRepository[T] is abstract and must be subclassed for each entity type.
Subclasses must implement the abstract methods to define entity-specific behavior.
"""

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from loguru import logger
from pydantic import BaseModel

from .connection import DatabaseConnection

# Generic type variable for entity models
T = TypeVar("T", bound=BaseModel)


class RepositoryError(Exception):
    """Raised when repository operations fail.

    This can occur when:
    - Entity not found
    - Validation fails
    - Database operation fails
    - Constraint violation
    """

    pass


class BaseRepository[T: BaseModel](ABC):
    """Generic base repository for type-safe database operations.

    This abstract base class provides common database operations for entities
    using the repository pattern. It uses Python generics to ensure type safety
    across all operations.

    Type parameter T must be a Pydantic BaseModel subclass representing the
    domain entity.

    Subclasses must implement:
    - table_name: Table name in database
    - id_column: Primary key column name
    - _row_to_entity: Convert database row to domain entity
    - _entity_to_row: Convert domain entity to database row
    - _get_insert_columns: Get column names for INSERT
    - _get_update_columns: Get column names for UPDATE

    Attributes:
        db: DatabaseConnection instance for database access.

    Example:
        >>> class CharacterRepository(BaseRepository[Character]):
        ...     table_name = "Characters"
        ...     id_column = "Id"
        ...
        ...     def _row_to_entity(self, row: sqlite3.Row) -> Character:
        ...         return Character(**dict(row))
        ...
        ...     def _entity_to_row(self, entity: Character) -> dict[str, Any]:
        ...         return entity.model_dump()
        ...
        ...     # ... implement other abstract methods
        >>>
        >>> db = DatabaseConnection(Path("erenshor.sqlite"))
        >>> repo = CharacterRepository(db)
        >>> character = repo.get_by_id(1)
    """

    def __init__(self, db: DatabaseConnection) -> None:
        """Initialize repository with database connection.

        Args:
            db: DatabaseConnection instance for database access.
        """
        self.db = db
        logger.debug(f"{self.__class__.__name__} initialized")

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Get the database table name for this repository.

        Returns:
            Database table name (e.g., "Characters", "Items", "Spells").
        """
        pass

    @property
    @abstractmethod
    def id_column(self) -> str:
        """Get the primary key column name for this repository.

        Returns:
            Primary key column name (e.g., "Id", "ItemDBIndex", "SpellDBIndex").
        """
        pass

    @abstractmethod
    def _row_to_entity(self, row: Any) -> T:
        """Convert database row to domain entity.

        This method handles the mapping from database representation (sqlite3.Row)
        to domain entity (Pydantic model). It should handle any necessary type
        conversions and validation.

        Args:
            row: Database row (sqlite3.Row with dict-like access).

        Returns:
            Domain entity instance.

        Raises:
            RepositoryError: If conversion fails or validation errors occur.
        """
        pass

    @abstractmethod
    def _entity_to_row(self, entity: T) -> dict[str, Any]:
        """Convert domain entity to database row.

        This method handles the mapping from domain entity (Pydantic model) to
        database representation (dictionary). It should handle any necessary
        type conversions for database storage.

        Args:
            entity: Domain entity instance.

        Returns:
            Dictionary of column names to values for database insertion/update.

        Raises:
            RepositoryError: If conversion fails.
        """
        pass

    @abstractmethod
    def _get_insert_columns(self) -> list[str]:
        """Get column names for INSERT operations.

        Returns:
            List of column names to include in INSERT statements.
            Typically excludes auto-increment primary keys.
        """
        pass

    @abstractmethod
    def _get_update_columns(self) -> list[str]:
        """Get column names for UPDATE operations.

        Returns:
            List of column names to include in UPDATE statements.
            Typically excludes primary key columns.
        """
        pass

    def get_by_id(self, entity_id: int) -> T | None:
        """Get entity by primary key ID.

        Args:
            entity_id: Primary key value.

        Returns:
            Entity instance if found, None if not found.

        Raises:
            RepositoryError: If database operation fails.

        Example:
            >>> character = repo.get_by_id(1)
            >>> if character:
            ...     print(character.object_name)
        """
        query = f"SELECT * FROM {self.table_name} WHERE {self.id_column} = ?"

        with self.db.connect() as conn:
            cursor = conn.execute(query, (entity_id,))
            row = cursor.fetchone()

            if row is None:
                logger.debug(f"{self.table_name}: Entity not found with id={entity_id}")
                return None

            try:
                entity = self._row_to_entity(row)
                logger.debug(f"{self.table_name}: Retrieved entity with id={entity_id}")
                return entity
            except Exception as e:
                raise RepositoryError(
                    f"Failed to convert row to entity: {e}\n" f"Table: {self.table_name}, ID: {entity_id}"
                ) from e

    def get_all(self) -> list[T]:
        """Get all entities from the table.

        Returns:
            List of all entities in the table. Empty list if none found.

        Raises:
            RepositoryError: If database operation fails.

        Example:
            >>> characters = repo.get_all()
            >>> print(f"Found {len(characters)} characters")
        """
        query = f"SELECT * FROM {self.table_name}"

        with self.db.connect() as conn:
            cursor = conn.execute(query)
            rows = cursor.fetchall()

            try:
                entities = [self._row_to_entity(row) for row in rows]
                logger.debug(f"{self.table_name}: Retrieved {len(entities)} entities")
                return entities
            except Exception as e:
                raise RepositoryError(f"Failed to convert rows to entities: {e}\n" f"Table: {self.table_name}") from e

    def create(self, entity: T) -> T:
        """Create a new entity in the database.

        Args:
            entity: Entity to create.

        Returns:
            Created entity (with ID populated if auto-increment).

        Raises:
            RepositoryError: If create operation fails.

        Example:
            >>> character = Character(id=0, object_name="NewCharacter", ...)
            >>> created = repo.create(character)
            >>> print(f"Created with ID: {created.id}")
        """
        try:
            row_data = self._entity_to_row(entity)
        except Exception as e:
            raise RepositoryError(f"Failed to convert entity to row: {e}\nTable: {self.table_name}") from e

        columns = self._get_insert_columns()
        placeholders = ", ".join(["?" for _ in columns])
        values = [row_data[col] for col in columns]

        query = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({placeholders})"

        with self.db.transaction() as conn:
            cursor = conn.execute(query, values)
            entity_id = cursor.lastrowid

            logger.debug(f"{self.table_name}: Created entity with id={entity_id}")

            # Fetch the created entity to get any database-generated values
            cursor = conn.execute(f"SELECT * FROM {self.table_name} WHERE {self.id_column} = ?", (entity_id,))
            row = cursor.fetchone()

            if row is None:
                raise RepositoryError(
                    f"Failed to retrieve created entity\n" f"Table: {self.table_name}, ID: {entity_id}"
                )

            return self._row_to_entity(row)

    def update(self, entity: T) -> T:
        """Update an existing entity in the database.

        Args:
            entity: Entity to update (must have valid ID).

        Returns:
            Updated entity.

        Raises:
            RepositoryError: If update operation fails or entity not found.

        Example:
            >>> character.npc_name = "Updated Name"
            >>> updated = repo.update(character)
        """
        try:
            row_data = self._entity_to_row(entity)
        except Exception as e:
            raise RepositoryError(f"Failed to convert entity to row: {e}\nTable: {self.table_name}") from e

        # Get entity ID
        entity_id = row_data.get(self.id_column)
        if entity_id is None:
            raise RepositoryError(
                f"Cannot update entity without ID\n" f"Table: {self.table_name}\n" f"ID column: {self.id_column}"
            )

        columns = self._get_update_columns()
        set_clause = ", ".join([f"{col} = ?" for col in columns])
        values = [row_data[col] for col in columns]
        values.append(entity_id)  # Add ID for WHERE clause

        query = f"UPDATE {self.table_name} SET {set_clause} WHERE {self.id_column} = ?"

        with self.db.transaction() as conn:
            cursor = conn.execute(query, values)

            if cursor.rowcount == 0:
                raise RepositoryError(f"Entity not found for update\n" f"Table: {self.table_name}\n" f"ID: {entity_id}")

            logger.debug(f"{self.table_name}: Updated entity with id={entity_id}")

            # Fetch the updated entity
            cursor = conn.execute(f"SELECT * FROM {self.table_name} WHERE {self.id_column} = ?", (entity_id,))
            row = cursor.fetchone()

            if row is None:
                raise RepositoryError(
                    f"Failed to retrieve updated entity\n" f"Table: {self.table_name}, ID: {entity_id}"
                )

            return self._row_to_entity(row)

    def delete(self, entity_id: int) -> bool:
        """Delete an entity by primary key ID.

        Args:
            entity_id: Primary key value.

        Returns:
            True if entity was deleted, False if not found.

        Raises:
            RepositoryError: If delete operation fails.

        Example:
            >>> deleted = repo.delete(1)
            >>> if deleted:
            ...     print("Entity deleted")
        """
        query = f"DELETE FROM {self.table_name} WHERE {self.id_column} = ?"

        with self.db.transaction() as conn:
            cursor = conn.execute(query, (entity_id,))
            deleted = cursor.rowcount > 0

            if deleted:
                logger.debug(f"{self.table_name}: Deleted entity with id={entity_id}")
            else:
                logger.debug(f"{self.table_name}: No entity found to delete with id={entity_id}")

            return deleted

    def insert_many(self, entities: list[T]) -> list[T]:
        """Bulk insert multiple entities.

        This is more efficient than calling create() multiple times as it uses
        a single transaction for all insertions.

        Args:
            entities: List of entities to insert.

        Returns:
            List of created entities (with IDs populated).

        Raises:
            RepositoryError: If bulk insert fails.

        Example:
            >>> characters = [Character(...), Character(...), Character(...)]
            >>> created = repo.insert_many(characters)
            >>> print(f"Created {len(created)} entities")
        """
        if not entities:
            return []

        columns = self._get_insert_columns()
        placeholders = ", ".join(["?" for _ in columns])
        query = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({placeholders})"

        with self.db.transaction() as conn:
            created_entities: list[T] = []

            for entity in entities:
                try:
                    row_data = self._entity_to_row(entity)
                    values = [row_data[col] for col in columns]

                    cursor = conn.execute(query, values)
                    entity_id = cursor.lastrowid

                    # Fetch created entity
                    cursor = conn.execute(f"SELECT * FROM {self.table_name} WHERE {self.id_column} = ?", (entity_id,))
                    row = cursor.fetchone()

                    if row is None:
                        raise RepositoryError(
                            f"Failed to retrieve created entity\n" f"Table: {self.table_name}, ID: {entity_id}"
                        )

                    created_entities.append(self._row_to_entity(row))

                except Exception as e:
                    raise RepositoryError(
                        f"Bulk insert failed: {e}\n"
                        f"Table: {self.table_name}\n"
                        f"Failed at entity {len(created_entities) + 1} of {len(entities)}"
                    ) from e

            logger.debug(f"{self.table_name}: Bulk inserted {len(created_entities)} entities")
            return created_entities

    def update_many(self, entities: list[T]) -> list[T]:
        """Bulk update multiple entities.

        This is more efficient than calling update() multiple times as it uses
        a single transaction for all updates.

        Args:
            entities: List of entities to update (must have valid IDs).

        Returns:
            List of updated entities.

        Raises:
            RepositoryError: If bulk update fails.

        Example:
            >>> characters = repo.get_all()
            >>> for char in characters:
            ...     char.level = char.level + 1
            >>> updated = repo.update_many(characters)
        """
        if not entities:
            return []

        columns = self._get_update_columns()
        set_clause = ", ".join([f"{col} = ?" for col in columns])
        query = f"UPDATE {self.table_name} SET {set_clause} WHERE {self.id_column} = ?"

        with self.db.transaction() as conn:
            updated_entities: list[T] = []

            for entity in entities:
                try:
                    row_data = self._entity_to_row(entity)

                    # Get entity ID
                    entity_id = row_data.get(self.id_column)
                    if entity_id is None:
                        raise RepositoryError(
                            f"Cannot update entity without ID\n"
                            f"Table: {self.table_name}\n"
                            f"ID column: {self.id_column}"
                        )

                    values = [row_data[col] for col in columns]
                    values.append(entity_id)

                    cursor = conn.execute(query, values)

                    if cursor.rowcount == 0:
                        raise RepositoryError(
                            f"Entity not found for update\n" f"Table: {self.table_name}\n" f"ID: {entity_id}"
                        )

                    # Fetch updated entity
                    cursor = conn.execute(f"SELECT * FROM {self.table_name} WHERE {self.id_column} = ?", (entity_id,))
                    row = cursor.fetchone()

                    if row is None:
                        raise RepositoryError(
                            f"Failed to retrieve updated entity\n" f"Table: {self.table_name}, ID: {entity_id}"
                        )

                    updated_entities.append(self._row_to_entity(row))

                except Exception as e:
                    raise RepositoryError(
                        f"Bulk update failed: {e}\n"
                        f"Table: {self.table_name}\n"
                        f"Failed at entity {len(updated_entities) + 1} of {len(entities)}"
                    ) from e

            logger.debug(f"{self.table_name}: Bulk updated {len(updated_entities)} entities")
            return updated_entities

    def execute_query(self, query: str, params: tuple[Any, ...] = ()) -> list[T]:
        """Execute a custom query and return typed results.

        This method provides an integration point for custom queries and query builders.
        The query must return rows that can be converted to the entity type T.

        Args:
            query: SQL query string.
            params: Query parameters (tuple).

        Returns:
            List of entities matching the query.

        Raises:
            RepositoryError: If query execution or conversion fails.

        Example:
            >>> # Custom query
            >>> characters = repo.execute_query(
            ...     "SELECT * FROM Characters WHERE level > ? AND is_unique = 1",
            ...     (50,)
            ... )
        """
        with self.db.connect() as conn:
            try:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                entities = [self._row_to_entity(row) for row in rows]
                logger.debug(f"{self.table_name}: Query returned {len(entities)} entities")
                return entities

            except Exception as e:
                raise RepositoryError(
                    f"Query execution failed: {e}\n" f"Table: {self.table_name}\n" f"Query: {query}"
                ) from e
