"""Tests for registry operations."""

import json

import pytest
from sqlmodel import Session, create_engine, select

from erenshor.registry.operations import (
    create_conflict_record,
    find_conflicts,
    get_entity,
    initialize_registry,
    list_entities,
    load_mapping_json,
    register_entity,
    resolve_conflict,
)
from erenshor.registry.schema import ConflictRecord, EntityRecord, EntityType


class TestInitializeRegistry:
    """Test initialize_registry function."""

    def test_initialize_creates_database(self, temp_db_path):
        """Test that initialize_registry creates database."""
        assert not temp_db_path.exists()

        initialize_registry(temp_db_path)

        assert temp_db_path.exists()

    def test_initialize_creates_tables(self, temp_db_path):
        """Test that initialize_registry creates all tables."""
        initialize_registry(temp_db_path)

        # Verify tables exist by querying them
        engine = create_engine(f"sqlite:///{temp_db_path}")
        try:
            with Session(engine) as session:
                # Should not raise errors
                session.exec(select(EntityRecord)).all()
                session.exec(select(ConflictRecord)).all()
        finally:
            engine.dispose()

    def test_initialize_idempotent(self, temp_db_path):
        """Test that calling initialize_registry multiple times is safe."""
        initialize_registry(temp_db_path)
        initialize_registry(temp_db_path)  # Should not fail

        assert temp_db_path.exists()

    def test_initialize_creates_parent_directory(self, tmp_path):
        """Test that initialize_registry creates parent directories."""
        nested_path = tmp_path / "nested" / "dir" / "registry.db"
        assert not nested_path.parent.exists()

        initialize_registry(nested_path)

        assert nested_path.exists()
        assert nested_path.parent.exists()


class TestRegisterEntity:
    """Test register_entity function."""

    def test_register_new_entity(self, in_memory_session):
        """Test registering a new entity with overrides."""
        entity = register_entity(
            in_memory_session,
            "item:iron_sword",
            page_title="Iron Sword (Weapon)",
            display_name="Iron Sword",
        )

        assert entity.stable_key == "item:iron_sword"
        assert entity.entity_type == EntityType.ITEM
        assert entity.page_title == "Iron Sword (Weapon)"
        assert entity.display_name == "Iron Sword"
        assert entity.excluded is False

    def test_register_entity_with_page_title(self, in_memory_session):
        """Test registering entity with custom page title."""
        entity = register_entity(
            in_memory_session,
            "item:iron_sword",
            page_title="Iron Sword (Weapon)",
        )

        assert entity.page_title == "Iron Sword (Weapon)"
        assert entity.display_name is None  # Not set
        assert entity.excluded is False

    def test_register_entity_upsert_updates_existing(self, in_memory_session):
        """Test that registering existing entity updates it (upsert)."""
        # Create initial entity
        entity1 = register_entity(
            in_memory_session,
            "item:iron_sword",
            page_title="Iron Sword",
        )
        entity1_key = entity1.stable_key

        # Register again with updated page title
        entity2 = register_entity(
            in_memory_session,
            "item:iron_sword",
            page_title="Iron Sword (Updated)",
        )

        # Should be same entity (same stable_key)
        assert entity2.stable_key == entity1_key
        assert entity2.page_title == "Iron Sword (Updated)"

        # Verify only one entity exists
        entities = in_memory_session.exec(select(EntityRecord)).all()
        assert len(entities) == 1

    def test_register_entity_different_types_same_name(self, in_memory_session):
        """Test registering entities with same resource_name but different types."""
        entity1 = register_entity(
            in_memory_session,
            "item:fireball",
            page_title="Fireball (Item)",
        )

        entity2 = register_entity(
            in_memory_session,
            "spell:fireball",
            page_title="Fireball (Spell)",
        )

        # Should create two separate entities
        assert entity1.stable_key != entity2.stable_key
        entities = in_memory_session.exec(select(EntityRecord)).all()
        assert len(entities) == 2


class TestGetEntity:
    """Test get_entity function."""

    def test_get_entity_found(self, in_memory_session):
        """Test retrieving entity by stable key."""
        # Create entity
        register_entity(
            in_memory_session,
            "item:iron_sword",
            page_title="Iron Sword (Weapon)",
            display_name="Iron Sword",
        )

        # Retrieve by stable key
        entity = get_entity(in_memory_session, "item:iron_sword")

        assert entity is not None
        assert entity.stable_key == "item:iron_sword"
        assert entity.entity_type == EntityType.ITEM
        assert entity.page_title == "Iron Sword (Weapon)"
        assert entity.display_name == "Iron Sword"

    def test_get_entity_not_found(self, in_memory_session):
        """Test retrieving non-existent entity returns None."""
        entity = get_entity(in_memory_session, "item:nonexistent")
        assert entity is None

    def test_get_entity_invalid_key_raises(self, in_memory_session):
        """Test that invalid stable key raises ValueError."""
        with pytest.raises(ValueError, match="Invalid stable key format"):
            get_entity(in_memory_session, "invalid_key")

        with pytest.raises(ValueError, match="Unknown entity type"):
            get_entity(in_memory_session, "unknown:test")


class TestListEntities:
    """Test list_entities function."""

    def test_list_all_entities(self, in_memory_session, sample_entities):
        """Test listing all entities."""
        for entity in sample_entities:
            in_memory_session.add(entity)
        in_memory_session.commit()

        entities = list_entities(in_memory_session)

        assert len(entities) == len(sample_entities)

    def test_list_entities_by_type(self, in_memory_session, sample_entities):
        """Test filtering entities by type."""
        for entity in sample_entities:
            in_memory_session.add(entity)
        in_memory_session.commit()

        # Filter by ITEM
        items = list_entities(in_memory_session, EntityType.ITEM)
        assert len(items) == 2
        assert all(e.entity_type == EntityType.ITEM for e in items)

        # Filter by CHARACTER
        characters = list_entities(in_memory_session, EntityType.CHARACTER)
        assert len(characters) == 2
        assert all(e.entity_type == EntityType.CHARACTER for e in characters)

        # Filter by SPELL
        spells = list_entities(in_memory_session, EntityType.SPELL)
        assert len(spells) == 1
        assert all(e.entity_type == EntityType.SPELL for e in spells)

    def test_list_entities_ordering(self, in_memory_session):
        """Test entities are ordered by stable_key."""
        # Create entities in random order
        register_entity(in_memory_session, "spell:fireball", page_title="Fireball")
        register_entity(in_memory_session, "item:steel_sword", page_title="Steel Sword")
        register_entity(in_memory_session, "item:iron_sword", page_title="Iron Sword")
        register_entity(in_memory_session, "character:goblin", page_title="Goblin")

        entities = list_entities(in_memory_session)

        # Should be ordered by stable_key (alphabetically: character, item, item, spell)
        assert len(entities) == 4
        assert entities[0].stable_key == "character:goblin"
        assert entities[1].stable_key == "item:iron_sword"
        assert entities[2].stable_key == "item:steel_sword"
        assert entities[3].stable_key == "spell:fireball"

    def test_list_entities_empty(self, in_memory_session):
        """Test listing entities when none exist."""
        entities = list_entities(in_memory_session)
        assert entities == []


class TestFindConflicts:
    """Test find_conflicts function."""

    def test_find_conflicts_detects_duplicates(self, in_memory_session):
        """Test that find_conflicts detects same display_name within type."""
        # Create two items with same display name override
        register_entity(
            in_memory_session,
            "item:iron_sword_1",
            display_name="Iron Sword",
        )
        register_entity(
            in_memory_session,
            "item:iron_sword_2",
            display_name="Iron Sword",
        )

        conflicts = find_conflicts(in_memory_session)

        assert len(conflicts) == 1
        display_name, entities = conflicts[0]
        assert display_name == "Iron Sword"
        assert len(entities) == 2

    def test_find_conflicts_per_entity_type(self, in_memory_session):
        """Test that conflicts are detected per-entity-type."""
        # Create item and spell with same display name (should NOT conflict)
        register_entity(
            in_memory_session,
            "item:fireball_item",
            display_name="Fireball",
        )
        register_entity(
            in_memory_session,
            "spell:fireball_spell",
            display_name="Fireball",
        )

        conflicts = find_conflicts(in_memory_session)

        # Should find no conflicts (different types)
        assert len(conflicts) == 0

    def test_find_conflicts_multiple_conflicts(self, in_memory_session):
        """Test finding multiple conflicts."""
        # Create first conflict (items)
        register_entity(in_memory_session, "item:sword_1", display_name="Sword")
        register_entity(in_memory_session, "item:sword_2", display_name="Sword")

        # Create second conflict (characters)
        register_entity(in_memory_session, "character:goblin_1", display_name="Goblin")
        register_entity(in_memory_session, "character:goblin_2", display_name="Goblin")
        register_entity(in_memory_session, "character:goblin_3", display_name="Goblin")

        conflicts = find_conflicts(in_memory_session)

        assert len(conflicts) == 2
        # Check first conflict
        display_name1, _entities1 = conflicts[0]
        assert display_name1 in ["Goblin", "Sword"]
        # Check second conflict
        display_name2, _entities2 = conflicts[1]
        assert display_name2 in ["Goblin", "Sword"]

    def test_find_conflicts_empty_when_no_duplicates(self, in_memory_session):
        """Test that no conflicts found when all names unique."""
        register_entity(in_memory_session, "item:iron_sword", display_name="Iron Sword")
        register_entity(in_memory_session, "item:steel_sword", display_name="Steel Sword")
        register_entity(in_memory_session, "spell:fireball", display_name="Fireball")

        conflicts = find_conflicts(in_memory_session)

        assert len(conflicts) == 0


class TestCreateConflictRecord:
    """Test create_conflict_record function."""

    def test_create_conflict_record(self, in_memory_session):
        """Test creating conflict record with entity_stable_keys as JSON."""
        conflict = create_conflict_record(
            in_memory_session,
            entity_stable_keys=["item:sword1", "item:sword2", "item:sword3"],
            conflict_type="name_collision",
        )

        assert conflict.id is not None
        assert conflict.entity_stable_keys == '["item:sword1", "item:sword2", "item:sword3"]'
        assert conflict.conflict_type == "name_collision"
        assert conflict.resolved is False

    def test_create_conflict_record_stored_in_db(self, in_memory_session):
        """Test that conflict record is persisted."""
        create_conflict_record(
            in_memory_session,
            entity_stable_keys=["item:sword1", "item:sword2"],
            conflict_type="name_collision",
        )

        conflicts = in_memory_session.exec(select(ConflictRecord)).all()
        assert len(conflicts) == 1


class TestResolveConflict:
    """Test resolve_conflict function."""

    def test_resolve_conflict_marks_resolved(self, in_memory_session):
        """Test that resolve_conflict marks conflict as resolved."""
        # Create conflict
        conflict = create_conflict_record(
            in_memory_session,
            entity_stable_keys=["item:sword1", "item:sword2", "item:sword3"],
            conflict_type="name_collision",
        )

        # Resolve conflict
        resolve_conflict(
            in_memory_session,
            conflict_id=conflict.id,
            chosen_stable_key="item:sword2",
            notes="Chose sword2 as canonical",
        )

        # Verify resolution
        in_memory_session.refresh(conflict)
        assert conflict.resolved is True
        assert conflict.resolution_stable_key == "item:sword2"
        assert conflict.resolution_notes == "Chose sword2 as canonical"
        assert conflict.resolved_at is not None

    def test_resolve_conflict_validates_chosen_entity(self, in_memory_session):
        """Test that resolve_conflict validates chosen_stable_key is in conflict."""
        # Create conflict with stable keys
        conflict = create_conflict_record(
            in_memory_session,
            entity_stable_keys=["item:sword1", "item:sword2", "item:sword3"],
            conflict_type="name_collision",
        )

        # Try to resolve with stable key not in conflict
        with pytest.raises(ValueError, match="Entity item:nonexistent is not part of conflict"):
            resolve_conflict(
                in_memory_session,
                conflict_id=conflict.id,
                chosen_stable_key="item:nonexistent",
            )

    def test_resolve_conflict_invalid_conflict_id_raises(self, in_memory_session):
        """Test that resolve_conflict raises ValueError for invalid conflict_id."""
        with pytest.raises(ValueError, match="Conflict not found: 999"):
            resolve_conflict(
                in_memory_session,
                conflict_id=999,
                chosen_stable_key="item:sword1",
            )

    def test_resolve_conflict_without_notes(self, in_memory_session):
        """Test resolving conflict without notes."""
        conflict = create_conflict_record(
            in_memory_session,
            entity_stable_keys=["item:sword1", "item:sword2"],
            conflict_type="name_collision",
        )

        resolve_conflict(
            in_memory_session,
            conflict_id=conflict.id,
            chosen_stable_key="item:sword1",
        )

        in_memory_session.refresh(conflict)
        assert conflict.resolved is True
        assert conflict.resolution_notes is None


class TestMigrateFromMappingJson:
    """Test load_mapping_json function."""

    def test_migrate_imports_mappings(self, in_memory_session, sample_mapping_json):
        """Test that load_mapping_json imports mappings."""
        count = load_mapping_json(in_memory_session, sample_mapping_json)

        # Should import 3 mappings (2 with overrides + 1 excluded)
        assert count == 3

        # Verify entity records were created
        entities = in_memory_session.exec(select(EntityRecord)).all()
        assert len(entities) == 3

    def test_migrate_imports_excluded_entities(self, in_memory_session, sample_mapping_json):
        """Test that entries with null wiki_page_name are imported as excluded."""
        load_mapping_json(in_memory_session, sample_mapping_json)

        entities = in_memory_session.exec(select(EntityRecord)).all()

        # Should include the excluded spell entry with excluded=True
        excluded_entity = next(
            (e for e in entities if e.stable_key == "spell:none - offering stone"),
            None,
        )
        assert excluded_entity is not None
        assert excluded_entity.excluded is True
        assert excluded_entity.page_title is None

    def test_migrate_handles_missing_file(self, in_memory_session, tmp_path):
        """Test that missing file returns 0 without raising error."""
        nonexistent_path = tmp_path / "nonexistent.json"

        count = load_mapping_json(in_memory_session, nonexistent_path)

        assert count == 0

    def test_migrate_returns_count(self, in_memory_session, tmp_path):
        """Test that migrate returns correct count."""
        # Create mapping with 5 valid entries
        mapping_data = {
            "rules": {
                f"item:test_{i}": {
                    "wiki_page_name": f"Test Item {i}",
                    "display_name": None,
                    "image_name": None,
                    "mapping_type": "custom",
                    "reason": None,
                }
                for i in range(5)
            }
        }

        mapping_file = tmp_path / "mapping.json"
        with mapping_file.open("w") as f:
            json.dump(mapping_data, f)

        count = load_mapping_json(in_memory_session, mapping_file)

        assert count == 5

    def test_migrate_empty_rules(self, in_memory_session, tmp_path):
        """Test migrating file with empty rules."""
        mapping_data = {"rules": {}}

        mapping_file = tmp_path / "mapping.json"
        with mapping_file.open("w") as f:
            json.dump(mapping_data, f)

        count = load_mapping_json(in_memory_session, mapping_file)

        assert count == 0

    def test_migrate_creates_entity_records(self, in_memory_session, sample_mapping_json):
        """Test that entity records have correct structure."""
        load_mapping_json(in_memory_session, sample_mapping_json)

        entities = in_memory_session.exec(select(EntityRecord)).all()

        for entity in entities:
            assert entity.stable_key is not None
            assert entity.entity_type is not None
            assert ":" in entity.stable_key  # Verify stable_key format
