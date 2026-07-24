"""Manage one lazily cached SQLite connection per manager instance.

The connection is created on first use and reused until :meth:`close` is called.
``connect()`` scopes access to that connection but does not own it or close it
when the scope exits. Call ``close()`` explicitly, or use the manager as an
outer context manager, to release the connection.

Transactions are managed separately by ``transaction()``: successful scopes
commit, database errors and other exceptions roll back, and only database
errors are wrapped in :class:`DatabaseConnectionError`.
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
    - Connection cleanup operations fail
    """

    pass


class DatabaseConnection:
    """Manage one lazily cached SQLite connection.

    The connection is created on first use and reused for the lifetime of this
    manager. ``connect()`` provides an access scope but does not close the
    connection when that scope exits. Call ``close()`` explicitly, or use this
    manager as an outer context manager, to close it.

    ``transaction()`` starts an explicit transaction, commits on successful
    completion, and rolls back on database or other exceptions. Database
    exceptions are wrapped in :class:`DatabaseConnectionError`, while other
    exceptions are re-raised after rollback.

    Attributes:
        database_path: Path to SQLite database file.
        read_only: If True, connection is opened in read-only mode.
        _connection: Lazily cached connection, or None after close.
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
        """Get or lazily create the cached database connection.

        Reuses the existing connection for this manager until ``close()`` is
        called. This is one connection per manager, not a connection pool.

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
            # The access scope does not own the cached connection. It remains
            # open for reuse until close() or the outer manager context exits.
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
        """Close the cached connection and release its resources.

        Closing is explicit: ``connect()`` scopes do not close the connection.
        The operation is idempotent, and also runs when the manager is used as
        an outer context manager or is garbage-collected.
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
