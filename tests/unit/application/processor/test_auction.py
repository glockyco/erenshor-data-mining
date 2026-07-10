"""Tests for code-fact-gated item auctionability."""

import sqlite3

import pytest

from erenshor.application.processor.auction import (
    EXPECTED_AUCTION_GATES,
    derive_is_auctionable,
    validate_auction_gates,
)
from erenshor.application.processor.entities import process_items
from erenshor.application.processor.writer import Writer


@pytest.mark.parametrize(
    ("item_level", "item_value", "no_trade_no_destroy", "required_slot", "expected"),
    [
        (10, 5, 0, "Head", True),
        (1, 1, 0, "Primary", True),
        (-1, 5, 0, "Head", True),
        (0, 5, 0, "Head", False),
        (10, 0, 0, "Head", False),
        (10, -1, 0, "Head", True),
        (10, 5, 1, "Head", False),
        (10, 5, 0, "General", False),
        (10, 5, 0, None, False),
        (None, 5, 0, "Head", False),
        (10, None, 0, "Head", False),
    ],
)
def test_predicate_truth_table(item_level, item_value, no_trade_no_destroy, required_slot, expected):
    assert derive_is_auctionable(item_level, item_value, no_trade_no_destroy, required_slot) is expected


def test_drift_gate_rejects_changed_comparison():
    bad = dict(EXPECTED_AUCTION_GATES)
    bad[("auction.player_listing_gates", "item_level")] = "== 0"

    with pytest.raises(ValueError, match="auction gate drift"):
        validate_auction_gates(bad)


def test_drift_gate_rejects_missing_comparison():
    missing = dict(EXPECTED_AUCTION_GATES)
    del missing[("auction.player_listing_gates", "item_value")]

    with pytest.raises(ValueError, match="auction gate drift"):
        validate_auction_gates(missing)


def test_clean_item_schema_has_auctionability_column(tmp_path):
    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()

    columns = {row[1] for row in writer.conn.execute("PRAGMA table_info(items)")}
    assert "is_auctionable" in columns

    writer.conn.close()


def test_process_items_loads_player_gates_and_writes_flags(tmp_path):
    raw = sqlite3.connect(":memory:")
    raw.execute(
        """
        CREATE TABLE code_facts (
            fact_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT
        )
        """
    )
    raw.executemany(
        "INSERT INTO code_facts VALUES (?, ?, ?)",
        [
            ("auction.player_listing_gates", "item_level", "!= 0"),
            ("auction.player_listing_gates", "item_value", "!= 0"),
            ("auction.player_listing_gate", "ok", "true"),
        ],
    )
    raw.execute(
        """
        CREATE TABLE Items (
            StableKey TEXT,
            ItemName TEXT,
            ResourceName TEXT,
            ItemLevel INTEGER,
            ItemValue INTEGER,
            NoTradeNoDestroy INTEGER,
            RequiredSlot TEXT
        )
        """
    )
    raw.executemany(
        "INSERT INTO Items VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("item:head", "Head", "HEAD", 10, 5, 0, "Head"),
            ("item:general", "General", "GENERAL", 10, 5, 0, "General"),
            ("item:locked", "Locked", "LOCKED", 10, 5, 1, "Head"),
            ("item:zero", "Zero", "ZERO", 0, 5, 0, "Head"),
        ],
    )
    for table in ("ItemStats", "ItemClasses", "CraftingRecipes", "CraftingRewards", "ItemDrops"):
        raw.execute(f"CREATE TABLE {table} (placeholder TEXT)")

    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()
    process_items(raw, writer, {})

    rows = writer.conn.execute("SELECT stable_key, is_auctionable FROM items ORDER BY stable_key").fetchall()
    assert [(row[0], row[1]) for row in rows] == [
        ("item:general", 0),
        ("item:head", 1),
        ("item:locked", 0),
        ("item:zero", 0),
    ]

    raw.close()
    writer.conn.close()
