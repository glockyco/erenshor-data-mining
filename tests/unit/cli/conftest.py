"""Shared fixtures for CLI command tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from erenshor.application.processor.writer import Writer
from erenshor.cli.context import CLIContext
from erenshor.infrastructure.config.loader import get_repo_root
from erenshor.infrastructure.config.schema import (
    Config,
    GlobalConfig,
    MapsConfig,
    MediaWikiConfig,
    UnityConfig,
    VariantConfig,
)


@pytest.fixture
def cli_context(tmp_path: Path) -> CLIContext:
    """Return a CLI context whose variant satisfies the clean-database preconditions.

    Commands guarded by ``@require_preconditions`` refuse to run without an
    existing, readable clean database that holds items. Point the variant at a
    throwaway database with the real clean schema and one item, so those guards
    pass on their own terms instead of being disabled and commands read the
    tables they expect. Every other variant path stays inside the temporary
    directory, so a command can never touch real variant state.
    """
    database_path = tmp_path / "erenshor-test.sqlite"
    writer = Writer(database_path)
    writer.create_schema()
    writer.insert_items([{"stable_key": "item:test", "display_name": "Test Item", "image_name": "Test Item"}])
    writer.conn.close()

    variant = VariantConfig(
        name="Main",
        app_id="0",
        unity_project=str(tmp_path / "unity"),
        editor_scripts=str(tmp_path / "editor"),
        database_raw=str(tmp_path / "raw.sqlite"),
        database=str(database_path),
        logs=str(tmp_path / "logs"),
        backups=str(tmp_path / "backups"),
        wiki=str(tmp_path / "wiki"),
        maps=MapsConfig(
            source_dir=str(tmp_path / "maps"),
            build_dir=str(tmp_path / "maps" / "build"),
        ),
    )

    # A closed local port: a command that reaches a real MediaWiki client fails
    # at once instead of reading the live wiki.
    mediawiki = MediaWikiConfig(api_url="http://127.0.0.1:9/api.php")
    return CLIContext(
        config=Config(
            global_=GlobalConfig(
                unity=UnityConfig(version="2021.3.45f2", path=str(tmp_path / "Unity")), mediawiki=mediawiki
            ),
            variants={"main": variant},
        ),
        variant="main",
        dry_run=False,
        repo_root=get_repo_root(),
    )
