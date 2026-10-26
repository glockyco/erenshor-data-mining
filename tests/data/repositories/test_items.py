"""Tests for ItemRepository."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from typing import TYPE_CHECKING, Any

import pytest

from erenshor.application.processor.writer import Writer
from erenshor.domain.entities.item import Item
from erenshor.domain.value_objects.item_provenance import (
    PROVENANCE_SCHEMA_VERSION,
    ItemAcquisition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceLocation,
    fact_to_dict,
)
from erenshor.infrastructure.database.connection import DatabaseConnection, DatabaseConnectionError
from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repository import RepositoryError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def item_repo(integration_db: Path) -> ItemRepository:
    """Create ItemRepository with integration database."""
    db = DatabaseConnection(integration_db, read_only=False)
    return ItemRepository(db)


@pytest.fixture
def canonical_writer(tmp_path: Path) -> Iterator[Writer]:
    writer = Writer(tmp_path / "canonical.sqlite")
    writer.create_schema()
    writer.conn.execute(
        "INSERT INTO item_provenance_meta VALUES (?, 'fixture-build', '{}')", (PROVENANCE_SCHEMA_VERSION,)
    )
    try:
        yield writer
    finally:
        writer.conn.close()


def _insert(writer: Writer, table: str, values: dict[str, object]) -> None:
    writer.conn.execute(
        f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})",
        tuple(values.values()),
    )


def _insert_fact(writer: Writer, fact: ItemAcquisition | ItemUse) -> None:
    data: dict[str, Any] = fact_to_dict(fact)
    conditions = data.pop("conditions")
    locations = data.pop("locations")
    evidence = data.pop("evidence")
    family = "acquisition" if isinstance(fact, ItemAcquisition) else "use"
    key = fact.acquisition_key if isinstance(fact, ItemAcquisition) else fact.use_key
    _insert(writer, f"item_{family}s", data)
    for condition in conditions:
        _insert(writer, f"item_{family}_conditions", {"owner_key": key, **condition})
    for location in locations:
        _insert(
            writer,
            f"item_{family}_locations",
            {
                "owner_key": key,
                **location,
                "conditions": json.dumps(location["conditions"]),
                "entry_zone_line_keys": json.dumps(location["entry_zone_line_keys"]),
            },
        )
    for row in evidence:
        _insert(writer, "item_provenance_evidence", {"owner_key": key, **row})


def _item(writer: Writer, key: str, name: str | None = None, **metadata: object) -> None:
    _insert(
        writer,
        "items",
        {
            "stable_key": key,
            "display_name": name or key,
            "wiki_page_name": name or key,
            "image_name": name or key,
            **metadata,
        },
    )


def _repo(writer: Writer, tmp_path: Path) -> ItemRepository:
    writer.conn.commit()
    return ItemRepository(DatabaseConnection(tmp_path / "canonical.sqlite", read_only=True))


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
    assert any(item.must_be_equipped_to_click == 1 for item in items)


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


def test_item_repository_rejects_a_missing_database(tmp_path: Path) -> None:
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


@pytest.mark.parametrize("version", [None, PROVENANCE_SCHEMA_VERSION + 1])
def test_source_projections_require_supported_canonical_schema(tmp_path: Path, version: int | None) -> None:
    """Raw facts never substitute for missing or unsupported canonical facts."""
    db_path = tmp_path / "smithing.sqlite"
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("CREATE TABLE code_facts (fact_id TEXT, key TEXT, value TEXT)")
        conn.execute("INSERT INTO code_facts VALUES ('smithing.upgrade_ids', 'strings', '31377423,2298018,2265228')")
        if version is not None:
            conn.execute("CREATE TABLE item_provenance_meta (schema_version INTEGER)")
            conn.execute("INSERT INTO item_provenance_meta VALUES (?)", (version,))
    repo = ItemRepository(DatabaseConnection(db_path, read_only=True))
    with pytest.raises(RepositoryError, match="item provenance schema"):
        repo.is_item_obtainable("item:ore - planar stone")


@pytest.mark.parametrize(
    ("access", "stage", "disposition", "probability", "conditions", "locations", "expected"),
    [
        ("verified_player", "final_acquisition", "current", 25, (), (), True),
        ("verified_player", "final_acquisition", None, 25, (), (), False),
        ("verified_player", "final_acquisition", "removed", 25, (), (), False),
        ("unconfirmed_player", "final_acquisition", "current", 25, (), (), False),
        ("internal_only", "final_acquisition", "current", 25, (), (), False),
        ("non_acquirable", "final_acquisition", "current", 25, (), (), False),
        ("verified_player", "native_pool", "current", 25, (), (), False),
        ("verified_player", "final_acquisition", "current", 0, (), (), False),
        (
            "verified_player",
            "final_acquisition",
            "current",
            25,
            (ProvenanceCondition("gate", 0, 0, "never"),),
            (),
            False,
        ),
        (
            "verified_player",
            "final_acquisition",
            "current",
            25,
            (
                ProvenanceCondition("gate", 0, 0, "never"),
                ProvenanceCondition("gate", 1, 0, "quest_done", "quest:open"),
            ),
            (),
            True,
        ),
        (
            "verified_player",
            "final_acquisition",
            "current",
            25,
            (ProvenanceCondition("level", 0, 0, "actor_level", actor="player", minimum=20, maximum=10),),
            (),
            False,
        ),
        (
            "verified_player",
            "final_acquisition",
            "current",
            25,
            (),
            (ProvenanceLocation("closed", "fixed", conditions=(ProvenanceCondition("gate", 0, 0, "never"),)),),
            False,
        ),
        (
            "verified_player",
            "final_acquisition",
            "current",
            25,
            (),
            (
                ProvenanceLocation("closed", "fixed", conditions=(ProvenanceCondition("gate", 0, 0, "never"),)),
                ProvenanceLocation("open", "fixed"),
            ),
            True,
        ),
    ],
)
def test_obtainability_and_teaching_share_canonical_player_access(
    *,
    canonical_writer: Writer,
    tmp_path: Path,
    access: Any,
    stage: Any,
    disposition: str | None,
    probability: float,
    conditions: tuple[ProvenanceCondition, ...],
    locations: tuple[ProvenanceLocation, ...],
    expected: bool,
) -> None:
    _item(canonical_writer, "item:scroll", teach_spell_stable_key="spell:learn", teach_skill_stable_key="skill:learn")
    _insert_fact(
        canonical_writer,
        ItemAcquisition(
            "origin",
            "item:scroll",
            "ui_grant",
            "character:panel",
            player_access_state=access,
            probability_stage=stage,
            probability_kind="exact",
            probability_min=probability,
            probability_max=probability,
            conditions=conditions,
            locations=locations,
        ),
    )
    if disposition is not None:
        _insert(
            canonical_writer,
            "item_dispositions",
            {
                "item_stable_key": "item:scroll",
                "disposition": disposition,
                "current_pages": "[]",
                "former_pages": "[]",
            },
        )
    canonical_writer.conn.execute("DROP VIEW vendor_offers")
    for table in (
        "loot_drops",
        "quest_variants",
        "character_dialogs",
        "water_fishables",
        "mining_node_items",
        "crafting_rewards",
        "item_bags",
    ):
        canonical_writer.conn.execute(f"DROP TABLE {table}")
    repo = _repo(canonical_writer, tmp_path)

    assert repo.is_item_obtainable("item:scroll") is expected
    assert [link.stable_key for link in repo.get_obtainable_items_that_teach_spell("spell:learn")] == (
        ["item:scroll"] if expected else []
    )
    assert [link.stable_key for link in repo.get_obtainable_items_that_teach_skill("skill:learn")] == (
        ["item:scroll"] if expected else []
    )


def test_crafting_recipe_preserves_slots_and_displays_only_actionable_rewards(
    canonical_writer: Writer,
    tmp_path: Path,
) -> None:
    for key in ("item:recipe", "item:material-alpha", "item:material-beta", "item:reward", "item:other"):
        _item(canonical_writer, key, "Shared page")
    for slot, item_key, quantity in (
        (10, "item:material-beta", 7),
        (2, "item:material-alpha", 3),
        (1, "item:material-alpha", 2),
    ):
        _insert_fact(
            canonical_writer,
            ItemUse(
                f"material:{slot}",
                item_key,
                "item:recipe",
                "crafting_material",
                material_slot=slot,
                quantity_min=quantity,
                quantity_max=quantity,
                quantity_kind="exact",
            ),
        )
    for slot, quantity in ((10, 9), (2, 4), (1, 2)):
        _insert_fact(
            canonical_writer,
            ItemAcquisition(
                f"outcome:{slot}",
                "item:reward",
                "crafting",
                "item:recipe",
                variant_key=str(slot),
                quantity_min=quantity,
                quantity_max=quantity,
                quantity_kind="exact",
                player_access_state="non_acquirable" if slot == 2 else "verified_player",
            ),
        )
        _insert_fact(
            canonical_writer,
            ItemUse(
                f"recipe:{slot}",
                "item:recipe",
                "item:reward",
                "crafting_recipe",
                variant_key=str(slot),
                quantity_min=1,
                quantity_max=1,
                quantity_kind="exact",
                outcome_key=f"outcome:{slot}",
            ),
        )
    _insert_fact(
        canonical_writer,
        ItemUse(
            "unrelated",
            "item:other",
            "item:recipe",
            "item_conversion",
            quantity_min=99,
            quantity_max=99,
            quantity_kind="exact",
        ),
    )
    canonical_writer.conn.execute("DROP TABLE crafting_recipes")
    canonical_writer.conn.execute("DROP TABLE crafting_rewards")
    repo = _repo(canonical_writer, tmp_path)

    recipe = repo.get_crafting_recipe("item:recipe")

    assert recipe is not None
    assert [(link.stable_key, quantity) for link, quantity in recipe.materials] == [
        ("item:material-alpha", 2),
        ("item:material-alpha", 3),
        ("item:material-beta", 7),
    ]
    assert [(link.stable_key, quantity) for link, quantity in recipe.results] == [
        ("item:reward", 2),
        ("item:reward", 9),
    ]
    assert repo.get_crafting_recipe("item:other") is None
    provenance = ItemProvenanceRepository(DatabaseConnection(tmp_path / "canonical.sqlite", read_only=True))
    assert {fact.variant_key for fact in provenance.get_uses("item:recipe")} == {"1", "2", "10"}
    assert {
        (fact.variant_key, fact.quantity_min, fact.player_access_state)
        for fact in provenance.get_acquisitions("item:reward")
    } == {
        ("1", 2, "verified_player"),
        ("2", 4, "non_acquirable"),
        ("10", 9, "verified_player"),
    }


def test_crafting_recipe_rejects_an_unlinked_canonical_outcome(
    canonical_writer: Writer,
    tmp_path: Path,
) -> None:
    _item(canonical_writer, "item:recipe")
    _item(canonical_writer, "item:reward")
    _insert_fact(
        canonical_writer,
        ItemUse(
            "recipe:1",
            "item:recipe",
            "item:reward",
            "crafting_recipe",
            variant_key="1",
            outcome_key="missing",
        ),
    )
    with pytest.raises(RepositoryError, match="Missing canonical crafting outcome"):
        _repo(canonical_writer, tmp_path).get_crafting_recipe("item:recipe")


@pytest.mark.parametrize(
    ("kind", "quantity_min", "quantity_max", "quantity_kind", "message"),
    [
        ("material", None, None, "unknown", "Missing exact crafting material quantity"),
        ("material", 1, 2, "bounded", "Missing exact crafting material quantity"),
        ("reward", None, None, "unknown", "Missing exact crafting reward quantity"),
        ("reward", 1.5, 1.5, "exact", "Non-integral item quantity"),
    ],
)
def test_crafting_recipe_does_not_invent_quantities(
    *,
    canonical_writer: Writer,
    tmp_path: Path,
    kind: str,
    quantity_min: float | None,
    quantity_max: float | None,
    quantity_kind: str,
    message: str,
) -> None:
    _item(canonical_writer, "item:recipe")
    _item(canonical_writer, "item:component")
    if kind == "material":
        _insert_fact(
            canonical_writer,
            ItemUse(
                "material:1",
                "item:component",
                "item:recipe",
                "crafting_material",
                material_slot=1,
                quantity_min=quantity_min,
                quantity_max=quantity_max,
                quantity_kind=quantity_kind,
            ),
        )
    else:
        _insert_fact(
            canonical_writer,
            ItemAcquisition(
                "outcome:1",
                "item:component",
                "crafting",
                "item:recipe",
                variant_key="1",
                quantity_min=quantity_min,
                quantity_max=quantity_max,
                quantity_kind=quantity_kind,
            ),
        )
        _insert_fact(
            canonical_writer,
            ItemUse(
                "recipe:1",
                "item:recipe",
                "item:component",
                "crafting_recipe",
                variant_key="1",
                outcome_key="outcome:1",
            ),
        )
    with pytest.raises(RepositoryError, match=message):
        _repo(canonical_writer, tmp_path).get_crafting_recipe("item:recipe")
