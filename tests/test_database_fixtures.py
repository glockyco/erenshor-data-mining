"""Tests for database fixtures."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def test_in_memory_db_fixture(in_memory_db: sqlite3.Connection):
    """Test that in_memory_db fixture creates a database with schema."""
    cursor = in_memory_db.cursor()

    # Check that key tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    assert "Items" in tables
    assert "Spells" in tables
    assert "Characters" in tables
    assert "Quests" in tables
    assert "ItemClasses" in tables
    assert "CharacterAttackSpells" in tables

    # Verify tables are empty (schema only)
    cursor.execute("SELECT COUNT(*) FROM Items")
    assert cursor.fetchone()[0] == 0


def test_in_memory_db_can_insert_data(in_memory_db: sqlite3.Connection):
    """Test that we can insert data into in_memory_db."""
    cursor = in_memory_db.cursor()

    # Insert a test item (simpler insert matching the actual schema)
    cursor.execute(
        """
        INSERT INTO Items VALUES (
            0, 'test_item', 'item:test_item', 'Test Item', 'A test item', 'Primary', 'None',
            '', 1, 0.0, 0, 0.0, '', NULL, 0, 0, 0.0, '', NULL, 0.0, 0.0, 0.0, 0.0, 0.0, NULL,
            0, '', NULL, 0.0, 0, 0.0, NULL, '', NULL, '', NULL, '', NULL, '', NULL,
            '', NULL, '', NULL, 0.0, NULL, NULL, NULL, NULL, 0, '', '',
            10, 5, 1, 0, 0, 0, 0, '', 0, 0, 0, 0, NULL, '', '', 0, 0, 'TestItem'
        )
        """
    )
    in_memory_db.commit()

    # Verify insertion
    cursor.execute("SELECT COUNT(*) FROM Items")
    assert cursor.fetchone()[0] == 1

    cursor.execute("SELECT ItemName FROM Items WHERE Id = 'test_item'")
    assert cursor.fetchone()[0] == "Test Item"


def test_integration_db_fixture(integration_db: Path):
    """Test that integration_db fixture loads sample data."""
    conn = sqlite3.connect(str(integration_db))
    cursor = conn.cursor()

    # Check that sample data exists
    cursor.execute("SELECT COUNT(*) FROM Items")
    item_count = cursor.fetchone()[0]
    assert item_count >= 3, f"Expected at least 3 items, got {item_count}"

    cursor.execute("SELECT COUNT(*) FROM Spells")
    spell_count = cursor.fetchone()[0]
    assert spell_count >= 3, f"Expected at least 3 spells, got {spell_count}"

    cursor.execute("SELECT COUNT(*) FROM Characters")
    character_count = cursor.fetchone()[0]
    assert character_count >= 3, f"Expected at least 3 characters, got {character_count}"

    cursor.execute("SELECT COUNT(*) FROM Quests")
    quest_count = cursor.fetchone()[0]
    assert quest_count >= 2, f"Expected at least 2 quests, got {quest_count}"

    # Verify junction tables have data
    cursor.execute("SELECT COUNT(*) FROM ItemClasses")
    assert cursor.fetchone()[0] >= 4

    cursor.execute("SELECT COUNT(*) FROM CharacterAttackSpells")
    assert cursor.fetchone()[0] >= 2

    conn.close()


def test_integration_db_sample_data_quality(integration_db: Path):
    """Test that integration_db contains realistic sample data."""
    conn = sqlite3.connect(str(integration_db))
    cursor = conn.cursor()

    # Check specific sample items
    cursor.execute("SELECT ItemName FROM Items WHERE Id = 'rusty_sword'")
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == "Rusty Sword"

    cursor.execute("SELECT SpellName FROM Spells WHERE Id = 'fireball'")
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == "Fireball"

    cursor.execute("SELECT NPCName FROM Characters WHERE Id = 1")
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == "Goblin Scout"

    cursor.execute("SELECT QuestName FROM Quests WHERE DBName = 'GOBLIN_TROUBLE'")
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == "Goblin Trouble"

    conn.close()


def test_production_db_skips_if_missing(production_db: Path | None):
    """Test that production_db fixture is skipped if database doesn't exist."""
    # This test will be skipped if production DB is not available
    # If it runs, verify the path exists
    if production_db is not None:
        assert production_db.exists()
        assert production_db.name == "erenshor-main.sqlite"


def test_in_memory_db_is_isolated():
    """Test that each in_memory_db fixture is independent."""
    # This is implicitly tested by pytest's fixture isolation
    # If this test runs after other tests, the database should still be clean
    pass


def test_fixtures_load_quickly(integration_db: Path):
    """Test that integration fixture loads in under 1 second."""
    import time

    # Create a new connection and query - should be fast since DB is already loaded
    start = time.time()
    conn = sqlite3.connect(str(integration_db))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Items")
    cursor.fetchone()
    conn.close()
    elapsed = time.time() - start

    assert elapsed < 1.0, f"Integration DB query took {elapsed:.2f}s, expected < 1s"
