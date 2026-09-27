"""Table-by-table comparison of two clean databases."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from erenshor.application.extract.database_comparison import ChangedRow, TableDiff, diff_databases, render_report


def _db(path: Path, script: str) -> Path:
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript(script)
    return path


def _tables(old: str, new: str, tmp_path: Path) -> dict[str, TableDiff]:
    diff = diff_databases(_db(tmp_path / "old.sqlite", old), _db(tmp_path / "new.sqlite", new))
    return {table.name: table for table in diff.tables}


ITEMS = "CREATE TABLE items (stable_key TEXT PRIMARY KEY, display_name TEXT, item_level INTEGER);"


def test_changed_value_names_the_column_with_old_and_new(tmp_path: Path) -> None:
    tables = _tables(
        ITEMS + "INSERT INTO items VALUES ('item:a', 'Sword', 10);",
        ITEMS + "INSERT INTO items VALUES ('item:a', 'Sword', 12);",
        tmp_path,
    )

    assert tables["items"].changed == (ChangedRow(("item:a",), (("item_level", 10, 12),)),)
    assert tables["items"].added == () and tables["items"].removed == ()


def test_rows_are_added_and_removed_by_primary_key(tmp_path: Path) -> None:
    tables = _tables(
        ITEMS + "INSERT INTO items VALUES ('item:a', 'Sword', 10);",
        ITEMS + "INSERT INTO items VALUES ('item:b', 'Axe', 5);",
        tmp_path,
    )

    assert tables["items"].added == (("item:b", "Axe", 5),)
    assert tables["items"].removed == (("item:a", "Sword", 10),)


def test_a_null_becoming_a_value_is_a_change(tmp_path: Path) -> None:
    tables = _tables(
        ITEMS + "INSERT INTO items VALUES ('item:a', NULL, 10);",
        ITEMS + "INSERT INTO items VALUES ('item:a', 'Sword', 10);",
        tmp_path,
    )

    assert tables["items"].changed == (ChangedRow(("item:a",), (("display_name", None, "Sword"),)),)


def test_table_without_primary_key_is_compared_as_a_multiset(tmp_path: Path) -> None:
    schema = "CREATE TABLE sources (quest TEXT, source TEXT);"
    tables = _tables(
        schema + "INSERT INTO sources VALUES ('q', 'npc'), ('q', 'npc'), ('q', 'item');",
        schema + "INSERT INTO sources VALUES ('q', 'npc'), ('q', 'item'), ('q', 'zone');",
        tmp_path,
    )

    assert tables["sources"].key_columns == ()
    assert tables["sources"].removed == (("q", "npc"),)
    assert tables["sources"].added == (("q", "zone"),)


def test_added_tables_and_columns_are_reported(tmp_path: Path) -> None:
    tables = _tables(
        ITEMS + "INSERT INTO items VALUES ('item:a', 'Sword', 10);",
        "CREATE TABLE items (stable_key TEXT PRIMARY KEY, display_name TEXT, item_level INTEGER, weight REAL);"
        "INSERT INTO items VALUES ('item:a', 'Sword', 10, 2.5);"
        "CREATE TABLE stances (stable_key TEXT PRIMARY KEY);",
        tmp_path,
    )

    assert tables["items"].added_columns == ("weight",)
    assert tables["items"].changed == ()
    assert tables["stances"].status == "added"


def test_report_lists_only_changed_tables_and_bounds_rows(tmp_path: Path) -> None:
    same = "CREATE TABLE zones (stable_key TEXT PRIMARY KEY); INSERT INTO zones VALUES ('zone:a');"
    rows = ", ".join(f"('item:{index}', 'Item {index}', 1)" for index in range(3))
    diff = diff_databases(
        _db(tmp_path / "old.sqlite", same + ITEMS),
        _db(tmp_path / "new.sqlite", same + ITEMS + f"INSERT INTO items VALUES {rows};"),
    )

    report = render_report(diff, "main build 1", "main build 2", limit=2)

    assert "1 of 2 tables changed." in report
    assert "## zones" not in report
    assert "**Added rows (3)**" in report
    assert "- … 1 more (use --limit 0 to list all)" in report
