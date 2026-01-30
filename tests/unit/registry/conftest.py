"""Pytest configuration and fixtures for registry tests."""

import json

import pytest
from sqlmodel import Session, SQLModel, create_engine

from erenshor.registry.schema import EntityRecord, EntityType


@pytest.fixture
def in_memory_engine():
    """Create in-memory SQLite database with registry schema."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def in_memory_session(in_memory_engine):
    """Create session for in-memory database."""
    with Session(in_memory_engine) as session:
        yield session


@pytest.fixture
def temp_db_path(tmp_path):
    """Create temporary database file path with auto-cleanup."""
    db_path = tmp_path / "test_registry.db"
    yield db_path
    # Cleanup happens automatically with tmp_path


@pytest.fixture
def sample_entities():
    """Create sample EntityRecord instances for testing."""
    return [
        EntityRecord(
            stable_key="item:iron_sword",
            entity_type=EntityType.ITEM,
            display_name="Iron Sword",
        ),
        EntityRecord(
            stable_key="item:steel_sword",
            entity_type=EntityType.ITEM,
            display_name="Steel Sword",
        ),
        EntityRecord(
            stable_key="spell:fireball",
            entity_type=EntityType.SPELL,
            display_name="Fireball",
        ),
        EntityRecord(
            stable_key="character:goblin_warrior",
            entity_type=EntityType.CHARACTER,
            display_name="Goblin Warrior",
        ),
        EntityRecord(
            stable_key="character:goblin_shaman",
            entity_type=EntityType.CHARACTER,
            display_name="Goblin Warrior",  # Duplicate display name for conflict testing
        ),
    ]


@pytest.fixture
def sample_mapping_json(tmp_path):
    """Create temporary mapping.json file for migration testing."""
    mapping_data = {
        "metadata": {
            "schema_version": "2.0",
            "created_at": "2025-09-21T15:44:48.853024Z",
            "updated_at": "2025-10-14T13:00:00.000000Z",
            "total_rules": 3,
        },
        "rules": {
            "character:Brackish Crocodile": {
                "wiki_page_name": "A Brackish Croc",
                "display_name": "A Brackish Croc",
                "image_name": "A Brackish Croc",
                "mapping_type": "custom",
                "reason": None,
            },
            "item:iron_sword_old": {
                "wiki_page_name": "Iron Sword",
                "display_name": "Iron Sword",
                "image_name": "Iron Sword",
                "mapping_type": "custom",
                "reason": "Renamed resource",
            },
            "spell:NONE - Offering Stone": {
                "wiki_page_name": None,
                "display_name": None,
                "image_name": None,
                "mapping_type": "exclude",
                "reason": None,
            },
        },
    }

    mapping_file = tmp_path / "mapping.json"
    with mapping_file.open("w") as f:
        json.dump(mapping_data, f, indent=2)

    yield mapping_file


@pytest.fixture
def conflict_entities():
    """Create sample entities with conflicts for testing validation."""
    return [
        # Conflict 1: "Iron Sword" - 3 entities (item)
        EntityRecord(
            stable_key="item:iron_sword",
            entity_type=EntityType.ITEM,
            page_title="Iron Sword",
            display_name="Iron Sword",
        ),
        EntityRecord(
            stable_key="item:iron_sword (1)",
            entity_type=EntityType.ITEM,
            page_title="Iron Sword",
            display_name="Iron Sword",
        ),
        EntityRecord(
            stable_key="item:iron_sword (2)",
            entity_type=EntityType.ITEM,
            page_title="Iron Sword",
            display_name="Iron Sword",
        ),
        # Conflict 2: "Goblin" - 2 entities (character)
        EntityRecord(
            stable_key="character:goblin",
            entity_type=EntityType.CHARACTER,
            page_title="Goblin",
            display_name="Goblin",
        ),
        EntityRecord(
            stable_key="character:goblin (1)",
            entity_type=EntityType.CHARACTER,
            page_title="Goblin",
            display_name="Goblin",
        ),
        # Non-conflict entity
        EntityRecord(
            stable_key="spell:fireball",
            entity_type=EntityType.SPELL,
            page_title="Fireball",
            display_name="Fireball",
        ),
    ]


@pytest.fixture
def partial_mapping_json(tmp_path):
    """Create mapping.json with partial conflict resolutions for validation testing."""
    mapping_data = {
        "metadata": {
            "schema_version": "2.0",
        },
        "rules": {
            # Fully resolved conflict: all 3 Iron Sword variants mapped
            "item:iron_sword": {
                "wiki_page_name": "Iron Sword",
                "display_name": "Iron Sword",
                "image_name": "Iron Sword",
                "mapping_type": "custom",
            },
            "item:iron_sword (1)": {
                "wiki_page_name": "Iron Sword",
                "display_name": "Iron Sword",
                "image_name": "Iron Sword",
                "mapping_type": "custom",
            },
            "item:iron_sword (2)": {
                "wiki_page_name": "Iron Sword",
                "display_name": "Iron Sword",
                "image_name": "Iron Sword",
                "mapping_type": "custom",
            },
            # Partially resolved conflict: only 1 of 2 Goblin variants mapped
            "character:goblin": {
                "wiki_page_name": "Goblin",
                "display_name": "Goblin",
                "image_name": "Goblin",
                "mapping_type": "custom",
            },
            # character:goblin (1) is MISSING - creates unresolved conflict
            # Non-conflict entity
            "spell:fireball": {
                "wiki_page_name": "Fireball",
                "display_name": "Fireball",
                "image_name": "Fireball",
                "mapping_type": "direct",
            },
        },
    }

    mapping_file = tmp_path / "partial_mapping.json"
    with mapping_file.open("w") as f:
        json.dump(mapping_data, f, indent=2)

    yield mapping_file


@pytest.fixture
def fully_resolved_mapping_json(tmp_path):
    """Create mapping.json with all conflicts fully resolved."""
    mapping_data = {
        "metadata": {
            "schema_version": "2.0",
        },
        "rules": {
            # All Iron Sword variants
            "item:iron_sword": {
                "wiki_page_name": "Iron Sword",
                "display_name": "Iron Sword",
                "image_name": "Iron Sword",
                "mapping_type": "custom",
            },
            "item:iron_sword (1)": {
                "wiki_page_name": "Iron Sword",
                "display_name": "Iron Sword",
                "image_name": "Iron Sword",
                "mapping_type": "custom",
            },
            "item:iron_sword (2)": {
                "wiki_page_name": "Iron Sword",
                "display_name": "Iron Sword",
                "image_name": "Iron Sword",
                "mapping_type": "custom",
            },
            # All Goblin variants
            "character:goblin": {
                "wiki_page_name": "Goblin",
                "display_name": "Goblin",
                "image_name": "Goblin",
                "mapping_type": "custom",
            },
            "character:goblin (1)": {
                "wiki_page_name": "Goblin",
                "display_name": "Goblin",
                "image_name": "Goblin",
                "mapping_type": "custom",
            },
            # Non-conflict entity
            "spell:fireball": {
                "wiki_page_name": "Fireball",
                "display_name": "Fireball",
                "image_name": "Fireball",
                "mapping_type": "direct",
            },
        },
    }

    mapping_file = tmp_path / "fully_resolved_mapping.json"
    with mapping_file.open("w") as f:
        json.dump(mapping_data, f, indent=2)

    yield mapping_file
