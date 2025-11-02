"""Tests for registry database schema."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from erenshor.registry.schema import ConflictRecord, EntityRecord, EntityType


class TestEntityRecord:
    """Test EntityRecord model."""

    def test_entity_record_creation(self, in_memory_session):
        """Test creating entity record with overrides."""
        entity = EntityRecord(
            entity_type=EntityType.ITEM,
            resource_name="iron_sword",
            page_title="Iron Sword (Weapon)",
            display_name="Iron Sword",
        )

        in_memory_session.add(entity)
        in_memory_session.commit()
        in_memory_session.refresh(entity)

        assert entity.id is not None
        assert entity.entity_type == EntityType.ITEM
        assert entity.resource_name == "iron_sword"
        assert entity.page_title == "Iron Sword (Weapon)"
        assert entity.display_name == "Iron Sword"
        assert entity.excluded is False

    def test_entity_record_all_entity_types(self, in_memory_session):
        """Test EntityRecord creation with all EntityType values."""
        entity_types = [
            EntityType.ITEM,
            EntityType.SPELL,
            EntityType.SKILL,
            EntityType.CHARACTER,
            EntityType.QUEST,
            EntityType.FACTION,
            EntityType.LOCATION,
            EntityType.ACHIEVEMENT,
            EntityType.CRAFTING_RECIPE,
            EntityType.LOOT_TABLE,
            EntityType.DIALOG,
            EntityType.OTHER,
        ]

        for entity_type in entity_types:
            entity = EntityRecord(
                entity_type=entity_type,
                resource_name=f"test_{entity_type.value}",
                page_title=f"Test {entity_type.value} Page",
            )
            in_memory_session.add(entity)

        in_memory_session.commit()

        # Verify all were created
        entities = in_memory_session.exec(select(EntityRecord)).all()
        assert len(entities) == len(entity_types)

    def test_unique_constraint_entity_type_resource_name(self, in_memory_session):
        """Test unique constraint on (entity_type, resource_name)."""
        # Create first entity
        entity1 = EntityRecord(
            entity_type=EntityType.ITEM,
            resource_name="iron_sword",
            page_title="Iron Sword",
        )
        in_memory_session.add(entity1)
        in_memory_session.commit()

        # Try to create duplicate (same entity_type and resource_name)
        entity2 = EntityRecord(
            entity_type=EntityType.ITEM,
            resource_name="iron_sword",
            page_title="Different Name",
        )
        in_memory_session.add(entity2)

        with pytest.raises(IntegrityError):
            in_memory_session.commit()

    def test_different_entity_types_same_resource_name_allowed(self, in_memory_session):
        """Test that same resource_name is allowed for different entity types."""
        # Create item
        entity1 = EntityRecord(
            entity_type=EntityType.ITEM,
            resource_name="fireball",
            page_title="Fireball (Item)",
        )
        in_memory_session.add(entity1)
        in_memory_session.commit()

        # Create spell with same resource_name (should succeed)
        entity2 = EntityRecord(
            entity_type=EntityType.SPELL,
            resource_name="fireball",
            page_title="Fireball (Spell)",
        )
        in_memory_session.add(entity2)
        in_memory_session.commit()

        # Verify both exist
        entities = in_memory_session.exec(select(EntityRecord)).all()
        assert len(entities) == 2

    def test_nullable_override_fields(self, in_memory_session):
        """Test nullable override fields (page_title, display_name, image_name)."""
        # Create entity without any overrides
        entity = EntityRecord(
            entity_type=EntityType.ITEM,
            resource_name="test_item",
        )
        in_memory_session.add(entity)
        in_memory_session.commit()
        in_memory_session.refresh(entity)

        assert entity.page_title is None
        assert entity.display_name is None
        assert entity.image_name is None
        assert entity.excluded is False

        # Update with overrides
        entity.page_title = "Test Item Page"
        entity.display_name = "Test Item Display"
        entity.image_name = "TestItem.png"
        in_memory_session.add(entity)
        in_memory_session.commit()
        in_memory_session.refresh(entity)

        assert entity.page_title == "Test Item Page"
        assert entity.display_name == "Test Item Display"
        assert entity.image_name == "TestItem.png"

    def test_excluded_field(self, in_memory_session):
        """Test excluded field for wiki exclusion."""
        entity = EntityRecord(
            entity_type=EntityType.SPELL,
            resource_name="test_spell",
            excluded=True,
        )
        in_memory_session.add(entity)
        in_memory_session.commit()
        in_memory_session.refresh(entity)

        assert entity.excluded is True
        assert entity.page_title is None  # Excluded entities have no overrides


class TestConflictRecord:
    """Test ConflictRecord model."""

    def test_conflict_record_creation(self, in_memory_session):
        """Test creating conflict record with entity_ids JSON."""
        conflict = ConflictRecord(
            entity_ids="[1, 2, 3]",
            conflict_type="name_collision",
            resolved=False,
            created_at=datetime.now(UTC),
        )

        in_memory_session.add(conflict)
        in_memory_session.commit()
        in_memory_session.refresh(conflict)

        assert conflict.id is not None
        assert conflict.entity_ids == "[1, 2, 3]"
        assert conflict.conflict_type == "name_collision"
        assert conflict.resolved is False
        assert conflict.resolution_entity_id is None

    def test_conflict_record_foreign_key(self, in_memory_session):
        """Test ConflictRecord foreign key to EntityRecord."""
        # Create entity
        entity = EntityRecord(
            entity_type=EntityType.ITEM,
            resource_name="test_item",
            page_title="Test Item",
        )
        in_memory_session.add(entity)
        in_memory_session.commit()
        in_memory_session.refresh(entity)

        # Create conflict with foreign key
        conflict = ConflictRecord(
            entity_ids=f"[{entity.id}]",
            conflict_type="name_collision",
            resolved=True,
            resolution_entity_id=entity.id,
            created_at=datetime.now(UTC),
            resolved_at=datetime.now(UTC),
        )
        in_memory_session.add(conflict)
        in_memory_session.commit()
        in_memory_session.refresh(conflict)

        assert conflict.resolution_entity_id == entity.id

    def test_conflict_record_resolution_fields(self, in_memory_session):
        """Test conflict resolution fields."""
        # Create unresolved conflict
        conflict = ConflictRecord(
            entity_ids="[1, 2]",
            conflict_type="name_collision",
            resolved=False,
            created_at=datetime.now(UTC),
        )
        in_memory_session.add(conflict)
        in_memory_session.commit()
        in_memory_session.refresh(conflict)

        assert conflict.resolved is False
        assert conflict.resolution_entity_id is None
        assert conflict.resolution_notes is None
        assert conflict.resolved_at is None

        # Resolve conflict
        conflict.resolved = True
        conflict.resolution_entity_id = 1
        conflict.resolution_notes = "Chose entity 1 as canonical"
        conflict.resolved_at = datetime.now(UTC)
        in_memory_session.add(conflict)
        in_memory_session.commit()
        in_memory_session.refresh(conflict)

        assert conflict.resolved is True
        assert conflict.resolution_entity_id == 1
        assert conflict.resolution_notes == "Chose entity 1 as canonical"
        assert conflict.resolved_at is not None


class TestTableCreation:
    """Test table creation via SQLModel."""

    def test_all_tables_created(self):
        """Test that all registry tables are created."""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        # Check that tables exist by querying them
        with Session(engine) as session:
            # Test entities table
            entities = session.exec(select(EntityRecord)).all()
            assert entities == []

            # Test conflicts table
            conflicts = session.exec(select(ConflictRecord)).all()
            assert conflicts == []
