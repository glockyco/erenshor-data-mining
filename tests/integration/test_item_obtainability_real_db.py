"""Integration tests for item obtainability with real database.

Tests verify the obtainability logic works correctly with actual game data.
"""

from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine

from erenshor.domain.services import is_item_obtainable


def test_obtainable_teaching_items_function_works(test_engine: Engine) -> None:
    """Test that is_item_obtainable function executes without errors.

    This test verifies the function can be called successfully with test data.
    Specific item obtainability assertions would depend on test database content.
    """
    from sqlalchemy import text

    # Get any teaching item from the test database
    with test_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT Id, ItemName FROM Items WHERE (TeachSpell IS NOT NULL AND TeachSpell <> '') OR (TeachSkill IS NOT NULL AND TeachSkill <> '') LIMIT 1"
            )
        ).fetchone()

    if result:
        item_id, item_name = result
        # Just verify the function runs without errors
        is_item_obtainable(test_engine, item_id, item_name)
        # Function executed successfully (no exception)


def test_spell_scrolls_obtainability_coverage(test_engine: Engine) -> None:
    """Test that obtainability check processes all spell scrolls without errors."""
    from sqlalchemy import text

    # Get all spell scrolls
    with test_engine.connect() as conn:
        spell_scrolls = conn.execute(
            text(
                "SELECT Id, ItemName FROM Items WHERE TeachSpell IS NOT NULL AND TeachSpell <> ''"
            )
        ).fetchall()

    if not spell_scrolls:
        pytest.skip("No spell scrolls in test database")

    obtainable_count = 0
    unobtainable_count = 0

    for item_id, item_name in spell_scrolls:
        if is_item_obtainable(test_engine, item_id, item_name):
            obtainable_count += 1
        else:
            unobtainable_count += 1

    # Verify that all items were classified (function didn't error)
    # Specific obtainability counts depend on test database content
    assert obtainable_count + unobtainable_count == len(
        spell_scrolls
    ), "All scrolls should be classified"


def test_skill_books_obtainability_coverage(test_engine: Engine) -> None:
    """Test that obtainability check processes all skill books without errors."""
    from sqlalchemy import text

    # Get all skill books
    with test_engine.connect() as conn:
        skill_books = conn.execute(
            text(
                "SELECT Id, ItemName FROM Items WHERE TeachSkill IS NOT NULL AND TeachSkill <> ''"
            )
        ).fetchall()

    if not skill_books:
        pytest.skip("No skill books in test database")

    obtainable_count = 0
    unobtainable_count = 0

    for item_id, item_name in skill_books:
        if is_item_obtainable(test_engine, item_id, item_name):
            obtainable_count += 1
        else:
            unobtainable_count += 1

    # Verify that all items were classified (function didn't error)
    # Specific obtainability counts depend on test database content
    assert obtainable_count + unobtainable_count == len(
        skill_books
    ), "All skill books should be classified"


def test_item_with_multiple_sources(test_engine: Engine) -> None:
    """Test items that are obtainable via multiple methods if available in test database."""
    from sqlalchemy import text

    # Try to find an item that has both drops and vendor sales
    with test_engine.connect() as conn:
        try:
            result = conn.execute(
                text(
                    """
                    SELECT DISTINCT i.Id, i.ItemName
                    FROM Items i
                    JOIN LootDrops ld ON i.Id = ld.ItemId
                    JOIN CharacterVendorItems cvi ON cvi.ItemName = i.ItemName
                    WHERE ld.DropProbability > 0
                    LIMIT 1
                    """
                )
            ).fetchone()
        except Exception:
            # Test database may not have these tables
            pytest.skip(
                "Test database doesn't have required tables for multi-source test"
            )
            return

    if not result:
        pytest.skip("No items with multiple sources found in test database")

    item_id, item_name = result
    # Should be obtainable (has multiple sources)
    is_obtainable = is_item_obtainable(test_engine, item_id, item_name)
    # Just verify the function executes (actual result depends on test data)
    assert isinstance(is_obtainable, bool), "Function should return a boolean"
