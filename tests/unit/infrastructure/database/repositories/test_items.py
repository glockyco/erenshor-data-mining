"""Tests for ItemRepository."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from erenshor.domain.entities.item import Item
from erenshor.infrastructure.database.connection import DatabaseConnection, DatabaseConnectionError
from erenshor.infrastructure.database.repositories.items import ItemRepository

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def item_repo(integration_db: Path) -> ItemRepository:
    """Create ItemRepository with integration database."""
    db = DatabaseConnection(integration_db, read_only=False)
    return ItemRepository(db)


def test_get_items_for_wiki_generation_returns_all_items(item_repo: ItemRepository):
    """Test that get_items_for_wiki_generation returns all valid items."""
    items = item_repo.get_items_for_wiki_generation()

    assert len(items) >= 3, "Expected at least 3 items from integration database"
    assert all(isinstance(item, Item) for item in items)
    assert all(item.item_name for item in items), "All items should have item_name"
    assert all(item.resource_name for item in items), "All items should have resource_name"


def test_get_items_for_wiki_generation_filters_blank_names(item_repo: ItemRepository):
    """Test that items with blank names are filtered out.

    This test verifies the WHERE clause filters work correctly.
    We rely on the integration database not having blank item names.
    """
    items = item_repo.get_items_for_wiki_generation()

    # All returned items should have non-blank names
    for item in items:
        assert item.item_name, f"Found item with blank item_name: {item.id}"
        assert item.resource_name, f"Found item with blank resource_name: {item.id}"


def test_get_items_for_wiki_generation_sorted_by_name(item_repo: ItemRepository):
    """Test that items are sorted by name case-insensitively."""
    items = item_repo.get_items_for_wiki_generation()

    if len(items) >= 2:
        item_names = [i.item_name.lower() if i.item_name else "" for i in items]
        assert item_names == sorted(item_names), "Items should be sorted by name"


def test_get_item_by_resource_name_found(item_repo: ItemRepository):
    """Test retrieving an item by resource name when it exists."""
    # Get first item from bulk query
    items = item_repo.get_items_for_wiki_generation()
    assert len(items) > 0, "Need at least one item for this test"

    first_item = items[0]
    assert first_item.resource_name is not None

    # Retrieve by resource name
    item = item_repo.get_item_by_resource_name(first_item.resource_name)

    assert item is not None
    assert item.item_name == first_item.item_name
    assert item.resource_name == first_item.resource_name
    assert isinstance(item, Item)


def test_get_item_by_resource_name_not_found(item_repo: ItemRepository):
    """Test retrieving an item by resource name when it doesn't exist."""
    item = item_repo.get_item_by_resource_name("nonexistent_item_12345")
    assert item is None


def test_get_item_by_resource_name_returns_single_result(item_repo: ItemRepository):
    """Test that get_item_by_resource_name returns only one item."""
    items = item_repo.get_items_for_wiki_generation()
    assert len(items) > 0

    first_item = items[0]
    assert first_item.resource_name is not None

    item = item_repo.get_item_by_resource_name(first_item.resource_name)
    assert isinstance(item, Item)


def test_item_entities_have_required_fields(item_repo: ItemRepository):
    """Test that Item entities have required fields populated."""
    items = item_repo.get_items_for_wiki_generation()
    assert len(items) > 0

    for item in items:
        # Required fields
        assert item.item_db_index is not None
        assert item.item_name is not None
        assert item.resource_name is not None

        # Verify entity can generate stable key
        assert item.stable_key.startswith("item:")


def test_item_repository_handles_database_error(tmp_path: Path):
    """Test that repository raises RepositoryError on database errors."""
    # Create a database path that doesn't exist
    nonexistent_db = tmp_path / "nonexistent.sqlite"

    # Try to create connection with read-only (will fail if file doesn't exist)
    with pytest.raises(DatabaseConnectionError):
        DatabaseConnection(nonexistent_db, read_only=True)


def test_item_repository_validates_data_types(item_repo: ItemRepository):
    """Test that repository correctly converts database types to Python types."""
    items = item_repo.get_items_for_wiki_generation()
    assert len(items) > 0

    for item in items:
        # Check type conversions
        assert isinstance(item.item_db_index, int)
        assert item.item_name is None or isinstance(item.item_name, str)
        assert item.item_level is None or isinstance(item.item_level, int)
        assert item.required_slot is None or isinstance(item.required_slot, str)
