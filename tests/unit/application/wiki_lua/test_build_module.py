from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from erenshor.application.wiki_lua.build import write_build_module
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.build_metadata import BuildMetadataRepository


def _build_repository(tmp_path: Path, *, with_row: bool) -> BuildMetadataRepository:
    db_path = tmp_path / "clean.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE code_facts_meta (game_build_id TEXT, game_build_published_at TEXT)")
        if with_row:
            connection.execute(
                "INSERT INTO code_facts_meta VALUES (?, ?)",
                ("24405256", "2026-07-27T12:34:56+00:00"),
            )
    return BuildMetadataRepository(DatabaseConnection(db_path, read_only=True))


def test_build_module_uses_clean_database_metadata(tmp_path: Path) -> None:
    output_path = write_build_module(_build_repository(tmp_path, with_row=True), tmp_path / "lua")

    assert output_path == tmp_path / "lua" / "Erenshor" / "Data" / "Build.lua"
    assert output_path.read_text(encoding="utf-8") == (
        'return {\n  ["gameBuildId"] = "24405256",\n  ["publishedAt"] = "2026-07-27T12:34:56+00:00",\n}\n'
    )


def test_build_module_fails_if_metadata_row_is_missing(tmp_path: Path) -> None:
    output_root = tmp_path / "lua"

    with pytest.raises(ValueError, match="code_facts_meta has no complete game build row"):
        write_build_module(_build_repository(tmp_path, with_row=False), output_root)

    assert not (output_root / "Erenshor" / "Data" / "Build.lua").exists()
