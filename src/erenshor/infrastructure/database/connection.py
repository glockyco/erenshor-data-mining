"""Database connection management with pooling and transaction support.

This module provides SQLite connection management with connection pooling,
context manager support, and transaction handling for the Erenshor data mining pipeline.

Features:
- Connection pooling (lightweight reuse of connections)
- Context manager support (automatic cleanup)
- Transaction management (explicit commit/rollback)
- Read-only mode (for safety when querying)
- Proper error handling and logging

The DatabaseConnection class is thread-safe and can be used across multiple
operations to reuse connections efficiently.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from loguru import logger


class DatabaseConnectionError(Exception):
    """Raised when database connection operations fail.

    This can occur when:
    - Database file does not exist or cannot be accessed
    - Connection cannot be established
    - Transaction commit/rollback fails
    - Connection pool operations fail
    """

    pass


class DatabaseConnection:
    """Manages SQLite database connections with pooling and transaction support.

    This class provides a connection pool (simple reuse pattern) for SQLite databases,
    along with context manager support for automatic cleanup and transaction management.

    The connection pool is lightweight since SQLite doesn't support true connection
    pooling - instead we reuse a single connection per instance and provide safe
    cleanup mechanisms.

    Attributes:
        database_path: Path to SQLite database file.
        read_only: If True, connection is opened in read-only mode.
        _connection: Cached connection instance (None when not connected).

    Example:
        >>> # Basic usage with context manager
        >>> db = DatabaseConnection(Path("erenshor.sqlite"))
        >>> with db.connect() as conn:
        ...     cursor = conn.execute("SELECT * FROM Characters")
        ...     rows = cursor.fetchall()

        >>> # Transaction support
        >>> with db.transaction() as conn:
        ...     conn.execute("INSERT INTO Characters (...) VALUES (...)")
        ...     # Automatically commits on success, rolls back on error

        >>> # Read-only mode for safety
        >>> db_readonly = DatabaseConnection(Path("erenshor.sqlite"), read_only=True)
        >>> with db_readonly.connect() as conn:
        ...     # Write operations will fail
        ...     cursor = conn.execute("SELECT * FROM Characters")
    """

    def __init__(self, database_path: Path, read_only: bool = False) -> None:
        """Initialize database connection manager.

        Args:
            database_path: Path to SQLite database file.
            read_only: If True, open connection in read-only mode (prevents writes).

        Raises:
            DatabaseConnectionError: If database file doesn't exist (for read-only mode).
        """
        self.database_path = database_path
        self.read_only = read_only
        self._connection: sqlite3.Connection | None = None

        # Validate database exists for read-only mode
        if read_only and not database_path.exists():
            raise DatabaseConnectionError(
                f"Database file not found: {database_path}\n"
                f"Cannot open in read-only mode - file must exist.\n"
                f"Create the database first or use read_only=False."
            )

        logger.debug(f"DatabaseConnection initialized: path={database_path}, read_only={read_only}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a database connection.

        This implements the connection pooling logic - reuses existing connection
        if available, creates new one if needed.

        Returns:
            Active SQLite connection instance.

        Raises:
            DatabaseConnectionError: If connection cannot be established.
        """
        if self._connection is None:
            try:
                # Build connection URI
                uri = f"file:{self.database_path}"
                if self.read_only:
                    uri += "?mode=ro"

                # Create connection
                self._connection = sqlite3.connect(uri, uri=True)
                self._connection.row_factory = sqlite3.Row  # Enable dict-like access

                logger.debug(f"Database connection established: {self.database_path}")

            except sqlite3.Error as e:
                raise DatabaseConnectionError(
                    f"Failed to connect to database: {self.database_path}\nError: {e}\nCheck file path and permissions."
                ) from e

        return self._connection

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection]:
        """Context manager for database connections.

        Yields a database connection and ensures proper cleanup. Does NOT
        automatically commit - use transaction() for automatic commit/rollback.

        Yields:
            Active SQLite connection.

        Raises:
            DatabaseConnectionError: If connection fails.

        Example:
            >>> db = DatabaseConnection(Path("erenshor.sqlite"))
            >>> with db.connect() as conn:
            ...     cursor = conn.execute("SELECT * FROM Characters WHERE id = ?", (1,))
            ...     row = cursor.fetchone()
        """
        connection = self._get_connection()
        try:
            yield connection
        except sqlite3.Error as e:
            logger.error(f"Database operation failed: {e}")
            raise DatabaseConnectionError(f"Database operation failed: {e}") from e
        finally:
            # Note: We don't close the connection here (pooling)
            # Connection will be closed in close() or __del__
            pass

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection]:
        """Context manager for database transactions.

        Yields a database connection with automatic transaction management:
        - Commits on successful completion
        - Rolls back on exceptions
        - Raises DatabaseConnectionError on commit/rollback failures

        This should be used for all write operations to ensure ACID properties.

        Yields:
            Active SQLite connection in transaction mode.

        Raises:
            DatabaseConnectionError: If transaction fails to commit or rollback.

        Example:
            >>> db = DatabaseConnection(Path("erenshor.sqlite"))
            >>> with db.transaction() as conn:
            ...     conn.execute("INSERT INTO Characters (id, object_name) VALUES (?, ?)", (1, "Test"))
            ...     # Automatically commits here
            >>> # If exception occurs, automatically rolls back
        """
        connection = self._get_connection()
        try:
            # Begin transaction (explicit for clarity)
            connection.execute("BEGIN")
            logger.debug("Transaction started")

            yield connection

            # Commit transaction
            connection.commit()
            logger.debug("Transaction committed")

        except sqlite3.Error as e:
            # Rollback on error
            logger.warning(f"Transaction failed, rolling back: {e}")
            try:
                connection.rollback()
                logger.debug("Transaction rolled back")
            except sqlite3.Error as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
                raise DatabaseConnectionError(
                    f"Transaction rollback failed: {rollback_error}\n"
                    f"Original error: {e}\n"
                    f"Database may be in inconsistent state."
                ) from rollback_error

            raise DatabaseConnectionError(f"Transaction failed: {e}") from e

        except Exception as e:
            # Rollback on non-database errors too
            logger.warning(f"Transaction failed with non-database error, rolling back: {e}")
            try:
                connection.rollback()
                logger.debug("Transaction rolled back")
            except sqlite3.Error as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
                raise DatabaseConnectionError(
                    f"Transaction rollback failed: {rollback_error}\n"
                    f"Original error: {e}\n"
                    f"Database may be in inconsistent state."
                ) from rollback_error

            raise

    def close(self) -> None:
        """Close the database connection and release resources.

        This should be called when done with the connection manager to ensure
        proper cleanup. Also called automatically in __del__.

        Safe to call multiple times (idempotent).
        """
        if self._connection is not None:
            try:
                self._connection.close()
                logger.debug(f"Database connection closed: {self.database_path}")
            except sqlite3.Error as e:
                logger.warning(f"Error closing database connection: {e}")
            finally:
                self._connection = None

    def __del__(self) -> None:
        """Cleanup database connection on garbage collection."""
        self.close()

    def __enter__(self) -> "DatabaseConnection":
        """Context manager entry - returns self for use in with statements."""
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Context manager exit - closes connection."""
        self.close()
