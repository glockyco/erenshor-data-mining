"""Pytest configuration and fixtures for registry tests."""

import json
from datetime import UTC, datetime

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
    now = datetime.now(UTC)
    return [
        EntityRecord(
            entity_type=EntityType.ITEM,
            resource_name="iron_sword",
            display_name="Iron Sword",
            first_seen=now,
            last_seen=now,
        ),
        EntityRecord(
            entity_type=EntityType.ITEM,
            resource_name="steel_sword",
            display_name="Steel Sword",
            first_seen=now,
            last_seen=now,
        ),
        EntityRecord(
            entity_type=EntityType.SPELL,
            resource_name="fireball",
            display_name="Fireball",
            first_seen=now,
            last_seen=now,
        ),
        EntityRecord(
            entity_type=EntityType.CHARACTER,
            resource_name="goblin_warrior",
            display_name="Goblin Warrior",
            first_seen=now,
            last_seen=now,
        ),
        EntityRecord(
            entity_type=EntityType.CHARACTER,
            resource_name="goblin_shaman",
            display_name="Goblin Warrior",  # Duplicate display name for conflict testing
            first_seen=now,
            last_seen=now,
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
                "display_name": None,
                "image_name": None,
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
                "wiki_page_name": None,  # Excluded entry
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
