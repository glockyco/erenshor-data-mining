"""Fixtures for data verification against the shipping main variant.

The data leaf is intentionally fail-fast.  Unlike the broad integration
fixtures, these paths are explicit verification inputs: a missing clean/raw
export or shipped game assembly is an environment error, not a skipped test.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from erenshor.infrastructure.config import load_config

if TYPE_CHECKING:
    from erenshor.application.guide.graph import EntityGraph

REPO_ROOT = Path(__file__).resolve().parents[2]

# Resolve through the configuration rather than the default layout: local config
# may point game_files at an installation the pipeline only reads, in which case
# the shipped assembly does not live under variants/main/game.
_MAIN_VARIANT = load_config().variants["main"]
MAIN_CLEAN_DB = _MAIN_VARIANT.resolved_database(REPO_ROOT)
MAIN_RAW_DB = _MAIN_VARIANT.resolved_database_raw(REPO_ROOT)
SHIPPED_MAIN_DLL = _MAIN_VARIANT.resolved_game_files(REPO_ROOT) / "Erenshor_Data" / "Managed" / "Assembly-CSharp.dll"
MAIN_WIKI_GENERATED = _MAIN_VARIANT.resolved_wiki(REPO_ROOT) / "generated"
CODE_FACTS_TOOL = REPO_ROOT / "src" / "tools" / "CodeFacts"


def _required_file(path: Path, description: str, command: str) -> Path:
    """Return a required data file, failing instead of silently skipping."""
    if not path.is_file():
        pytest.fail(
            f"{description} not found: {path}\nGenerate the required input with `{command}` before running tests/data.",
            pytrace=False,
        )
    return path


@pytest.fixture(scope="session")
def main_clean_db() -> Path:
    """Return the shipping main clean database, or fail when it is absent."""
    return _required_file(
        MAIN_CLEAN_DB,
        "Main clean database",
        "uv run erenshor -V main extract build",
    )


@pytest.fixture(scope="session")
def main_raw_db() -> Path:
    """Return the shipping main raw database, or fail when it is absent."""
    return _required_file(
        MAIN_RAW_DB,
        "Main raw database",
        "uv run erenshor -V main extract export",
    )


@pytest.fixture(scope="session")
def shipped_main_dll() -> Path:
    """Return the shipped main Assembly-CSharp binary, or fail when absent."""
    return _required_file(
        SHIPPED_MAIN_DLL,
        "Shipped main Assembly-CSharp.dll",
        "uv run erenshor -V main extract export",
    )


@pytest.fixture(scope="session")
def main_wiki_generated() -> Path:
    """Return the generated wiki tree, or fail when it has not been produced.

    Generation preserves manually authored sections of the live pages, so the
    fetch has to precede it: generating without one silently drops that content
    and the samples then fail on missing markers rather than on the real cause.
    """
    directory = MAIN_WIKI_GENERATED
    if not directory.is_dir() or not any(directory.glob("*.txt")):
        pytest.fail(
            f"Generated wiki pages not found: {directory}\nGenerate the required input with "
            "`uv run erenshor -V main wiki fetch && uv run erenshor -V main wiki generate` "
            "before running tests/data.",
            pytrace=False,
        )
    return directory


@pytest.fixture(scope="session", autouse=True)
def _main_data_preconditions(
    main_clean_db: Path,
    main_raw_db: Path,
    shipped_main_dll: Path,
    main_wiki_generated: Path,
) -> None:
    """Require all shipping data inputs for every explicit data-leaf test."""
    # Dependencies perform the checks.  Keeping this fixture autouse means a
    # test that does not otherwise need a particular file cannot accidentally
    # turn a missing data prerequisite into a skip.


@pytest.fixture(scope="session")
def graph(main_clean_db: Path) -> EntityGraph:
    """Build the production guide graph once for all data contracts."""
    from erenshor.application.guide.generator import generate

    overrides = REPO_ROOT / "quest_guides" / "graph_overrides.toml"
    return generate(main_clean_db, overrides if overrides.exists() else None)


@pytest.fixture(scope="session")
def exported_db(main_clean_db: Path) -> Path:
    """Compatibility name for data tests migrated from integration."""
    return main_clean_db


@pytest.fixture(scope="session")
def integration_db(main_clean_db: Path) -> Path:
    """Use the explicit shipping database for migrated graph tests."""
    return main_clean_db


@pytest.fixture(scope="session")
def sheets_engine(main_clean_db: Path) -> Generator[Any]:
    """Create a SQLAlchemy engine with the production sheet SQL function."""
    from sqlalchemy import create_engine, event

    engine = create_engine(f"sqlite:///{main_clean_db}")

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, _connection_record: Any) -> None:
        dbapi_connection.create_function(
            "map_marker_url",
            1,
            lambda key: f"https://erenshor.compendiums.org/map?sel=marker:{key}",
        )

    try:
        yield engine
    finally:
        engine.dispose()


def build_dotnet(project: Path, *extra: str) -> None:
    """Build a .NET project in Release and preserve diagnostics on failure."""
    dotnet = shutil.which("dotnet")
    if dotnet is None:
        pytest.fail("dotnet SDK not found on PATH; data tool tests require .NET", pytrace=False)

    proc = subprocess.run(
        [dotnet, "build", str(project), "-c", "Release", *extra],
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
    """Expose the diagnostic .NET build helper to data test modules."""
    return build_dotnet


@pytest.fixture(scope="session")
def code_facts_tool(shipped_main_dll: Path) -> Path:
    """Build CodeFacts once and return its project directory."""
    # Keep the shipped-DLL dependency explicit even though the suite-level
    # precondition also checks it; this fixture documents the tool contract.
    del shipped_main_dll
    build_dotnet(CODE_FACTS_TOOL)
    return CODE_FACTS_TOOL
