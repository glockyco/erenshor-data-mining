"""The clean-DB processor carries code_facts verbatim and treats a missing
raw table as an ordering error (extract step skipped), never a soft case."""

import sqlite3
from pathlib import Path

import pytest

from erenshor.application.processor.code_facts import process_code_facts
from erenshor.application.processor.writer import Writer


def _clean_writer(tmp_path: Path) -> Writer:
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    return writer


def test_missing_code_facts_tables_is_an_ordering_error(tmp_path: Path) -> None:
    raw = sqlite3.connect(tmp_path / "raw.sqlite")
    raw.row_factory = sqlite3.Row
    raw.execute("CREATE TABLE other (x)")  # raw export exists, code_facts does not

    writer = _clean_writer(tmp_path)
    with pytest.raises(ValueError, match="erenshor extract code-facts"):
        process_code_facts(raw, writer)


def test_code_facts_passthrough(tmp_path: Path) -> None:
    raw = sqlite3.connect(tmp_path / "raw.sqlite")
    raw.row_factory = sqlite3.Row
    raw.execute(
        "CREATE TABLE code_facts (fact_id TEXT, key TEXT, value TEXT, value_type TEXT, PRIMARY KEY (fact_id, key))"
    )
    raw.execute("CREATE TABLE code_facts_meta (assembly_sha256 TEXT, extracted_at TEXT, game_build_id TEXT)")
    raw.executemany(
        "INSERT INTO code_facts VALUES (?, ?, ?, ?)",
        [
            ("loot.world_drop.maps", "rate", "0.0125", "float"),
            ("loot.guarantee_one_drop", "ok", "true", "bool"),
        ],
    )
    raw.execute(
        "INSERT INTO code_facts_meta VALUES (?, ?, ?)",
        ("abc123def4567", "2026-06-11T00:00:00Z", "24362350"),
    )
    raw.commit()

    writer = _clean_writer(tmp_path)
    process_code_facts(raw, writer)
    writer.finalize()

    clean = sqlite3.connect(tmp_path / "clean.sqlite")
    facts = clean.execute("SELECT fact_id, key, value, value_type FROM code_facts ORDER BY fact_id, key").fetchall()
    assert facts == [
        ("loot.guarantee_one_drop", "ok", "true", "bool"),
        ("loot.world_drop.maps", "rate", "0.0125", "float"),
    ]
    meta = clean.execute("SELECT assembly_sha256, extracted_at, game_build_id FROM code_facts_meta").fetchall()
    assert meta == [("abc123def4567", "2026-06-11T00:00:00Z", "24362350")]


def test_empty_meta_is_an_ordering_error(tmp_path: Path) -> None:
    raw = sqlite3.connect(tmp_path / "raw.sqlite")
    raw.row_factory = sqlite3.Row
    raw.execute(
        "CREATE TABLE code_facts (fact_id TEXT, key TEXT, value TEXT, value_type TEXT, PRIMARY KEY (fact_id, key))"
    )
    raw.execute("CREATE TABLE code_facts_meta (assembly_sha256 TEXT, extracted_at TEXT, game_build_id TEXT)")
    raw.commit()  # half-written raw: tables exist but meta is empty

    writer = _clean_writer(tmp_path)
    with pytest.raises(ValueError, match="erenshor extract code-facts"):
        process_code_facts(raw, writer)
