"""Database connection management."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

__all__ = ["get_engine"]


def get_engine(db_path: str | Path) -> Engine:
    """Create SQLAlchemy engine for the given database path."""
    return create_engine(f"sqlite:///{Path(db_path)}")
