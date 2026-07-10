"""Tests for class starting-item clean-data migration."""

import sqlite3

from erenshor.application.processor.entities import process_class_starting_items
from erenshor.application.processor.writer import Writer


def test_class_starting_items_preserve_positions_and_filter_missing_items(tmp_path):
    """Only valid item references reach the ordered clean class inventory."""
    raw = sqlite3.connect(":memory:")
    raw.execute(
        """
        CREATE TABLE ClassStartingItems (
            ClassName TEXT NOT NULL,
            SortOrder INTEGER NOT NULL,
            ItemStableKey TEXT NOT NULL,
            PRIMARY KEY (ClassName, SortOrder)
        )
        """
    )
    raw.executemany(
        "INSERT INTO ClassStartingItems VALUES (?, ?, ?)",
        [
            ("Arcanist", 0, "item:wand"),
            ("Arcanist", 1, "item:wand"),
            ("Paladin", 0, "item:sword"),
            ("Druid", 0, "item:missing"),
            ("Reaver", 0, "item:sword"),
            ("Reaver", 1, "item:missing"),
            ("Reaver", 2, "item:wand"),
        ],
    )

    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()
    process_class_starting_items(raw, writer, {"item:wand", "item:sword"})

    rows = writer.conn.execute(
        """
        SELECT class_name, item_stable_key, sort_order
        FROM class_starting_items
        ORDER BY class_name, sort_order
        """
    ).fetchall()

    assert [tuple(row) for row in rows] == [
        ("Arcanist", "item:wand", 0),
        ("Arcanist", "item:wand", 1),
        ("Paladin", "item:sword", 0),
        ("Reaver", "item:sword", 0),
        ("Reaver", "item:wand", 2),
    ]

    raw.close()
    writer.conn.close()
