"""Database infrastructure module.

This module provides database connection management and repository patterns
for type-safe database access.
"""

from .connection import DatabaseConnection, DatabaseConnectionError
from .repository import BaseRepository, RepositoryError

__all__ = [
    "BaseRepository",
    "DatabaseConnection",
    "DatabaseConnectionError",
    "RepositoryError",
]
