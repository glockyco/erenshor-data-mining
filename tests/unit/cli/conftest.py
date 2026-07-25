"""Shared fixtures for CLI command tests."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from erenshor.cli.context import CLIContext
from erenshor.infrastructure.config.loader import get_repo_root
from erenshor.infrastructure.config.schema import Config, MapsConfig, VariantConfig


@pytest.fixture
def cli_context(tmp_path: Path) -> CLIContext:
    """Return a CLI context whose variant satisfies the clean-database preconditions.

    Commands guarded by ``@require_preconditions`` refuse to run without an
    existing, readable clean database that holds items. Point the variant at a
    throwaway database so those guards pass on their own terms instead of being
    disabled, and keep every other variant path inside the temporary directory
    so a command can never touch real variant state.
    """
    database_path = tmp_path / "erenshor-test.sqlite"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO items (id) VALUES (1)")
        connection.commit()

    variant = VariantConfig(
        name="Main",
        app_id="0",
        unity_project=str(tmp_path / "unity"),
        editor_scripts=str(tmp_path / "editor"),
        game_files=str(tmp_path / "game"),
        database_raw=str(tmp_path / "raw.sqlite"),
        database=str(database_path),
        logs=str(tmp_path / "logs"),
        backups=str(tmp_path / "backups"),
        wiki=str(tmp_path / "wiki"),
        maps=MapsConfig(
            source_dir=str(tmp_path / "maps"),
            database_dir=str(tmp_path / "maps" / "static" / "db"),
            build_dir=str(tmp_path / "maps" / "build"),
        ),
    )

    return CLIContext(
        config=Config(variants={"main": variant}),
        variant="main",
        dry_run=False,
        repo_root=get_repo_root(),
    )
