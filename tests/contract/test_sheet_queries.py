"""Run every sheet query against the clean-database schema.

The sheet queries read the clean database, which CI does not have. The data
leaf runs them against a real build, but only on a machine with game data. A
query that names a renamed or dropped column therefore passed CI. SQLite
resolves every table and column when it prepares a statement, so running each
query against the empty schema that the writer creates catches that drift
without any game data.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine

import erenshor.application.sheets as sheets_package
from erenshor.application.processor.writer import Writer
from erenshor.application.sheets.formatter import SheetsFormatter

QUERIES_DIR = Path(sheets_package.__file__).parent / "queries"


def test_every_sheet_query_runs_against_the_clean_schema(tmp_path: Path) -> None:
    database = tmp_path / "clean.sqlite"
    writer = Writer(database)
    writer.create_schema()
    writer.conn.close()
    formatter = SheetsFormatter(
        create_engine(f"sqlite:///{database}"), QUERIES_DIR, map_base_url="https://maps.example.invalid"
    )

    sheets = formatter.format_all_sheets()

    assert set(sheets) == {path.stem for path in QUERIES_DIR.glob("*.sql")}
    empty_headers = sorted(name for name, rows in sheets.items() if not rows or not rows[0])
    assert not empty_headers, f"Sheet queries without a header row: {empty_headers}"


def test_drop_sheet_names_swap_only_rows_without_merging_enemy_sources(tmp_path: Path) -> None:
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    try:
        writer.conn.execute(
            """INSERT INTO items (stable_key, display_name, image_name)
               VALUES ('item:bread', 'Bread', 'Bread')"""
        )
        writer.conn.executemany(
            """INSERT INTO characters
               (stable_key, display_name, image_name, encounter_tier, level_scales_with_player)
               VALUES (?, ?, ?, 'enemy', 0)""",
            [
                ("character:swap", "Swap enemy", "Swap enemy"),
                ("character:combined", "Combined enemy", "Combined enemy"),
                ("character:own", "Own enemy", "Own enemy"),
            ],
        )
        writer.conn.executemany(
            """INSERT INTO loot_drops
               (character_stable_key, item_stable_key, drop_probability, is_common_world_item, is_common)
               VALUES (?, 'item:bread', ?, ?, ?)""",
            [
                ("character:swap", 0.92, 1, 0),
                ("character:combined", 25.0, 1, 1),
                ("character:own", 30.0, 0, 1),
            ],
        )

        rows = writer.conn.execute((QUERIES_DIR / "drop-chances.sql").read_text(encoding="utf-8")).fetchall()

        assert {(row[0], row[1], row[2], row[3]) for row in rows} == {
            ("Common world item", "Swap enemy", "Bread", 0.92),
            ("Character", "Combined enemy", "Bread", 25.0),
            ("Character", "Own enemy", "Bread", 30.0),
        }
    finally:
        writer.conn.close()


def test_world_drop_sheet_preserves_default_pre_replacement_rolls_and_level_gate(tmp_path: Path) -> None:
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    try:
        writer.conn.executemany(
            "INSERT INTO items (stable_key, display_name, image_name) VALUES (?, ?, ?)",
            [("item:mask", "Unique mask", "Mask"), ("item:balance", "Balance", "Balance")],
        )
        writer.conn.executemany(
            "INSERT INTO special_world_drops VALUES (?, ?, ?, ?)",
            [
                ("item:mask", "Masks", 0.0065333333, 0),
                ("item:balance", "CrystallizedBalance", 0.05, 30),
            ],
        )

        rows = writer.conn.execute((QUERIES_DIR / "drop-chances.sql").read_text(encoding="utf-8")).fetchall()

        assert {(row[0], row[1], row[2], row[3]) for row in rows} == {
            (
                "World Drop",
                "Any enemy",
                "Unique mask",
                0.0065,
            ),
            (
                "World Drop",
                "Any enemy above level 30",
                "Balance",
                0.05,
            ),
        }
    finally:
        writer.conn.close()
