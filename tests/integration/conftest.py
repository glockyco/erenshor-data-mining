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
    """Return the playtest clean database used by integration tests.

    Golden baselines and exported-data integration tests are playtest-shaped.
    The fixture is explicit instead of mtime-based so unrelated local main/demo
    rebuilds cannot silently change test coverage.

    Raises:
        pytest.skip: If the playtest clean database does not exist.
    """
    db = Path(__file__).parent.parent.parent / "variants" / "playtest" / "erenshor-playtest.sqlite"
    if not db.exists():
        pytest.skip("Playtest clean database not found. Run 'uv run erenshor -V playtest extract build' first.")
    return db


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
