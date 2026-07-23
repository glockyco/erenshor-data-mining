"""Tests for ItemRepository."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

import pytest

from erenshor.domain.entities.item import Item
from erenshor.domain.value_objects.wiki_link import ItemLink
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
    assert all(item.stable_key for item in items), "All items should have stable_key"


def test_get_items_for_link_catalog_includes_nonnull_blank_pages(item_repo: ItemRepository):
    """Catalog stream retains blank pages so validation can reject them."""
    catalog_items = item_repo.get_items_for_link_catalog()

    assert all(item.wiki_page_name is not None for item in catalog_items)
    assert {item.stable_key for item in item_repo.get_items_for_wiki_generation()} <= {
        item.stable_key for item in catalog_items
    }


def test_get_items_for_wiki_generation_filters_blank_names(item_repo: ItemRepository):
    """Test that items with blank names are filtered out.

    This test verifies the WHERE clause filters work correctly.
    We rely on the integration database not having blank item names.
    """
    items = item_repo.get_items_for_wiki_generation()

    # All returned items should have non-blank names
    for item in items:
        assert item.item_name, f"Found item with blank item_name: {item.stable_key}"
        assert item.stable_key, f"Found item with blank stable_key: {item.stable_key}"


def test_get_items_for_wiki_generation_sorted_by_name(item_repo: ItemRepository):
    """Test that items are sorted by name case-insensitively."""
    items = item_repo.get_items_for_wiki_generation()

    if len(items) >= 2:
        item_names = [i.item_name.lower() if i.item_name else "" for i in items]
        assert item_names == sorted(item_names), "Items should be sorted by name"


def test_item_entities_have_required_fields(item_repo: ItemRepository):
    """Test that Item entities have required fields populated."""
    items = item_repo.get_items_for_wiki_generation()
    assert len(items) > 0

    for item in items:
        # Required fields
        assert item.item_name is not None
        assert item.stable_key is not None

        # Verify stable key format
        assert item.stable_key.startswith("item:")


def test_item_entities_include_item_flags(item_repo: ItemRepository):
    """Test that repository mapping preserves clean item flags."""
    items = item_repo.get_items_for_wiki_generation()

    assert any(item.rare_item == 1 for item in items)
    assert any(item.is_auctionable == 1 for item in items)
    assert any(item.is_auctionable == 0 for item in items)
    assert any(item.player_cannot_sell == 1 for item in items)


def test_get_item_stats_orders_all_quality_tiers(tmp_path: Path):
    """Test that item stats are returned in gameplay quality order."""
    db_path = tmp_path / "items.sqlite"
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(
            """
            CREATE TABLE item_stats (
                item_stable_key TEXT,
                quality TEXT,
                weapon_dmg INTEGER,
                hp INTEGER,
                ac INTEGER,
                mana INTEGER,
                str INTEGER,
                end INTEGER,
                dex INTEGER,
                agi INTEGER,
                int INTEGER,
                wis INTEGER,
                cha INTEGER,
                res INTEGER,
                mr INTEGER,
                er INTEGER,
                pr INTEGER,
                vr INTEGER,
                str_scaling REAL,
                end_scaling REAL,
                dex_scaling REAL,
                agi_scaling REAL,
                int_scaling REAL,
                wis_scaling REAL,
                cha_scaling REAL,
                resist_scaling REAL,
                mitigation_scaling REAL
            )
            """
        )
        for quality in (
            "Improved +5",
            "Blessed",
            "Improved +2",
            "Ascended",
            "Standard",
            "Improved +4",
            "Improved +1",
            "Improved +3",
        ):
            conn.execute(
                "INSERT INTO item_stats (item_stable_key, quality) VALUES (?, ?)",
                ("item:test", quality),
            )

    repo = ItemRepository(DatabaseConnection(db_path, read_only=True))

    qualities = [stats.quality for stats in repo.get_item_stats("item:test")]

    assert qualities == [
        "Standard",
        "Improved +1",
        "Improved +2",
        "Improved +3",
        "Improved +4",
        "Improved +5",
        "Blessed",
        "Ascended",
    ]


def test_item_relationship_links_keep_stable_keys_for_shared_pages(tmp_path: Path) -> None:
    """Relationship queries preserve identity when records share a wiki page."""
    db_path = tmp_path / "relationships.sqlite"
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("CREATE TABLE items (stable_key TEXT, display_name TEXT, wiki_page_name TEXT, image_name TEXT)")
        conn.execute("CREATE TABLE crafting_rewards (recipe_item_stable_key TEXT, reward_item_stable_key TEXT)")
        conn.executemany(
            "INSERT INTO items VALUES (?, ?, ?, ?)",
            [
                ("item:mold-alpha", "Alpha Mold", "Shared Mold", "Alpha Mold"),
                ("item:mold-beta", "Beta Mold", "Shared Mold", "Beta Mold"),
                ("item:reward", "Reward", "Reward", "Reward"),
            ],
        )
        conn.executemany(
            "INSERT INTO crafting_rewards VALUES (?, ?)",
            [("item:mold-alpha", "item:reward"), ("item:mold-beta", "item:reward")],
        )
        conn.commit()

    with DatabaseConnection(db_path, read_only=True) as db:
        links = ItemRepository(db).get_items_producing_item("item:reward")

    assert [(link.display_name, link.stable_key, str(link)) for link in links] == [
        (
            "Alpha Mold",
            "item:mold-alpha",
            "{{ItemLink|stablekey=item:mold-alpha}}",
        ),
        (
            "Beta Mold",
            "item:mold-beta",
            "{{ItemLink|stablekey=item:mold-beta}}",
        ),
    ]


def test_item_sources_keep_stable_keys_for_shared_pages(tmp_path: Path) -> None:
    """Item source links retain identity when source items share a wiki page."""
    db_path = tmp_path / "item-sources.sqlite"
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("CREATE TABLE items (stable_key TEXT, display_name TEXT, wiki_page_name TEXT)")
        conn.execute(
            "CREATE TABLE item_drops (source_item_stable_key TEXT, dropped_item_stable_key TEXT, drop_probability REAL)"
        )
        conn.executemany(
            "INSERT INTO items VALUES (?, ?, ?)",
            [
                ("item:source-alpha", "Alpha Source", "Shared Source"),
                ("item:source-beta", "Beta Source", "Shared Source"),
                ("item:dropped", "Dropped Item", "Dropped Item"),
            ],
        )
        conn.executemany(
            "INSERT INTO item_drops VALUES (?, ?, ?)",
            [
                ("item:source-alpha", "item:dropped", 25.0),
                ("item:source-beta", "item:dropped", 75.0),
            ],
        )

    with DatabaseConnection(db_path, read_only=True) as db:
        sources = ItemRepository(db).get_item_sources("item:dropped")

    assert all(isinstance(link, ItemLink) for link, _ in sources)
    assert [(link.stable_key, probability) for link, probability in sources] == [
        ("item:source-beta", 75.0),
        ("item:source-alpha", 25.0),
    ]

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
        assert isinstance(item.stable_key, str)
        assert item.item_name is None or isinstance(item.item_name, str)
        assert item.item_level is None or isinstance(item.item_level, int)
        assert item.required_slot is None or isinstance(item.required_slot, str)


def test_obtained_from_item_sources_cover_craft_use_and_starting(item_repo: ItemRepository) -> None:
    """Item provenance retains source keys, deterministic quantities, and classes."""
    craft = item_repo.get_recipes_rewarding_item("item:key - ghostly key")
    assert [(source.source_key, source.quantity) for source in craft] == [("item:template - a chewed key mold", 4)]

    use = item_repo.get_item_use_sources("item:gen - offering stone")
    assert [(source.source_key, source.probability) for source in use] == [("item:gen - bag of offering stones", None)]

    starting = item_repo.get_classes_starting_with_item("item:cons - bread")
    assert [source.source_key for source in starting] == [
        "class:Arcanist",
        "class:Druid",
        "class:Duelist",
        "class:Paladin",
        "class:Reaver",
        "class:Stormcaller",
    ]


def test_used_in_sources_cover_crafting_and_smithing(item_repo: ItemRepository) -> None:
    craft = item_repo.get_crafting_material_sources("item:ore - bronze ore")
    assert craft
    assert all(source.use_type == "craft_material" for source in craft)
    assert all(source.target_key.startswith("item:template") for source in craft)
    assert all(source.quantity is not None and source.slot is not None for source in craft)

    planar = item_repo.get_item_smithing_special_uses("item:ore - planar stone")
    assert [(source.use_type, source.target_key) for source in planar] == [
        ("upgrade_material", "item:template - an otherwordly mold")
    ]

    diamond = item_repo.get_item_smithing_special_uses("item:template - inert diamond")
    assert [(source.use_type, source.target_key) for source in diamond] == [
        ("blessing_removal_material", "item:template - inert diamond")
    ]

    merging_vessel = item_repo.get_item_smithing_special_uses("item:template - merging vessel")
    assert merging_vessel == []


@pytest.mark.parametrize("fact_value", [None, "31377423,2298018"])
def test_smithing_code_fact_drift_fails_fast(tmp_path: Path, fact_value: str | None) -> None:
    """Smithing special-use resolution rejects missing or changed facts."""
    db_path = tmp_path / "smithing.sqlite"
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("CREATE TABLE code_facts (fact_id TEXT, key TEXT, value TEXT)")
        if fact_value is not None:
            conn.execute(
                "INSERT INTO code_facts (fact_id, key, value) VALUES (?, ?, ?)",
                ("smithing.upgrade_ids", "strings", fact_value),
            )
        conn.commit()

    repo = ItemRepository(DatabaseConnection(db_path, read_only=True))
    with pytest.raises(ValueError, match="Smithing code-fact drift"):
        repo.get_item_smithing_special_uses("item:ore - planar stone")
