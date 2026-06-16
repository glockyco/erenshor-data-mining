"""Fixtures for integration tests using exported databases.

Integration tests use real exported databases from the variants/ directory
instead of hand-written fixtures. This ensures:
- Schema always matches production
- Tests verify real queries against real data patterns
- No maintenance burden from hand-written SQL
- Catches real-world edge cases
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

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
    databases = [db for db in databases if ".pre-" not in db.name and "-raw" not in db.name]

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


# ---------------------------------------------------------------------------
# CodeFacts .NET analyzer build
#
# The pre-push hook runs the whole integration suite, which rebuilds the
# pinned CodeFacts analyzer (src/tools/CodeFacts) before exercising it. A bare
# ``subprocess.run(check=True, capture_output=True)`` discards the MSBuild and
# NuGet diagnostics, so a transient restore/build failure surfaces only as an
# opaque ``CalledProcessError: ... exit status 1`` -- with no clue why, blocking
# even unrelated pushes. Route every integration build through one helper that
# folds the captured output into the failure message, and build the analyzer
# once per session so the failure window is not multiplied across modules.
# ---------------------------------------------------------------------------

_DOTNET = shutil.which("dotnet")
_CODE_FACTS_TOOL = Path(__file__).resolve().parents[2] / "src" / "tools" / "CodeFacts"


def build_dotnet(project: Path, *extra: str) -> None:
    """Build a .NET project in Release, surfacing MSBuild output on failure."""
    assert _DOTNET is not None, "dotnet SDK not on PATH; gate tests with skipif"
    proc = subprocess.run(
        [_DOTNET, "build", str(project), "-c", "Release", *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(
            f"dotnet build failed for {project} (exit {proc.returncode})\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def dotnet_build() -> Callable[..., None]:
    """Expose the diagnostic .NET build helper to integration test modules."""
    return build_dotnet


@pytest.fixture(scope="session")
def code_facts_tool() -> Path:
    """Build the CodeFacts analyzer once per session; return its project dir."""
    build_dotnet(_CODE_FACTS_TOOL)
    return _CODE_FACTS_TOOL
