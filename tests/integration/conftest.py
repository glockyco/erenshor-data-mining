"""Fixtures for integration tests using exported databases.

Integration tests use real exported databases from the variants/ directory
instead of hand-written fixtures. This ensures:
- Schema always matches production
- Tests verify real queries against real data patterns
- No maintenance burden from hand-written SQL
- Catches real-world edge cases
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.engine import Engine


@pytest.fixture(scope="session")
def exported_db() -> Path:
    """Find most recently exported database from any variant.

    Searches variants/ directory for erenshor-*.sqlite files and returns
    the most recently modified one. Filters out backup files (*.pre-*).

    Returns:
        Path: Path to the most recently exported database

    Raises:
        pytest.skip: If no exported database exists
    """
    variants_dir = Path(__file__).parent.parent.parent / "variants"
    databases = list(variants_dir.glob("*/erenshor-*.sqlite"))

    # Filter out backup/temp files
    databases = [db for db in databases if ".pre-" not in db.name]

    if not databases:
        pytest.skip("No exported database found. Run 'uv run erenshor extract export' first.")

    # Return most recently modified
    return max(databases, key=lambda p: p.stat().st_mtime)


@pytest.fixture(scope="session")
def sheets_engine(exported_db: Path) -> Generator[Engine]:
    """Create SQLAlchemy engine for sheets query tests.

    Registers the same custom SQL functions that SheetsFormatter provides
    so queries can be executed directly against the engine in tests.

    Args:
        exported_db: Path to exported database

    Yields:
        Engine: SQLAlchemy engine connected to exported database
    """
    from typing import Any

    from sqlalchemy import create_engine, event

    engine = create_engine(f"sqlite:///{exported_db}")

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, _connection_record: Any) -> None:
        dbapi_connection.create_function(
            "map_marker_url",
            1,
            lambda key: f"https://erenshor-maps.wowmuch1.workers.dev/map?sel=marker:{key}",
        )

    yield engine
    engine.dispose()
