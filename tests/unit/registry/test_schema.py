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
            stable_key="item:iron_sword",
            entity_type=EntityType.ITEM,
            page_title="Iron Sword (Weapon)",
            display_name="Iron Sword",
        )

        in_memory_session.add(entity)
        in_memory_session.commit()
        in_memory_session.refresh(entity)

        assert entity.stable_key == "item:iron_sword"
        assert entity.entity_type == EntityType.ITEM
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
            EntityType.ZONE,
        ]

        for entity_type in entity_types:
            entity = EntityRecord(
                stable_key=f"{entity_type.value}:test_{entity_type.value}",
                entity_type=entity_type,
                page_title=f"Test {entity_type.value} Page",
            )
            in_memory_session.add(entity)

        in_memory_session.commit()

        # Verify all were created
        entities = in_memory_session.exec(select(EntityRecord)).all()
        assert len(entities) == len(entity_types)

    def test_unique_constraint_entity_type_resource_name(self, in_memory_session):
        """Test unique constraint on stable_key (primary key)."""
        # Create first entity
        entity1 = EntityRecord(
            stable_key="item:iron_sword",
            entity_type=EntityType.ITEM,
            page_title="Iron Sword",
        )
        in_memory_session.add(entity1)
        in_memory_session.commit()

        # Close the session to clear the identity map
        in_memory_session.close()

        # Try to create duplicate (same stable_key) - should raise IntegrityError
        entity2 = EntityRecord(
            stable_key="item:iron_sword",
            entity_type=EntityType.ITEM,
            page_title="Different Name",
        )
        in_memory_session.add(entity2)

        with pytest.raises(IntegrityError):
            in_memory_session.commit()

    def test_different_entity_types_same_resource_name_allowed(self, in_memory_session):
        """Test that same resource_name is allowed for different entity types."""
        # Create item
        entity1 = EntityRecord(
            stable_key="item:fireball",
            entity_type=EntityType.ITEM,
            page_title="Fireball (Item)",
        )
        in_memory_session.add(entity1)
        in_memory_session.commit()

        # Create spell with same resource_name (different stable_key, should succeed)
        entity2 = EntityRecord(
            stable_key="spell:fireball",
            entity_type=EntityType.SPELL,
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
            stable_key="item:test_item",
            entity_type=EntityType.ITEM,
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
            stable_key="spell:test_spell",
            entity_type=EntityType.SPELL,
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
        """Test creating conflict record with entity_stable_keys JSON."""
        conflict = ConflictRecord(
            entity_stable_keys='["item:sword1", "item:sword2", "item:sword3"]',
            conflict_type="name_collision",
            resolved=False,
            created_at=datetime.now(UTC),
        )

        in_memory_session.add(conflict)
        in_memory_session.commit()
        in_memory_session.refresh(conflict)

        assert conflict.id is not None
        assert conflict.entity_stable_keys == '["item:sword1", "item:sword2", "item:sword3"]'
        assert conflict.conflict_type == "name_collision"
        assert conflict.resolved is False
        assert conflict.resolution_stable_key is None

    def test_conflict_record_foreign_key(self, in_memory_session):
        """Test ConflictRecord foreign key to EntityRecord."""
        # Create entity
        entity = EntityRecord(
            stable_key="item:test_item",
            entity_type=EntityType.ITEM,
            page_title="Test Item",
        )
        in_memory_session.add(entity)
        in_memory_session.commit()
        in_memory_session.refresh(entity)

        # Create conflict with foreign key
        conflict = ConflictRecord(
            entity_stable_keys=f'["{entity.stable_key}"]',
            conflict_type="name_collision",
            resolved=True,
            resolution_stable_key=entity.stable_key,
            created_at=datetime.now(UTC),
            resolved_at=datetime.now(UTC),
        )
        in_memory_session.add(conflict)
        in_memory_session.commit()
        in_memory_session.refresh(conflict)

        assert conflict.resolution_stable_key == entity.stable_key

    def test_conflict_record_resolution_fields(self, in_memory_session):
        """Test conflict resolution fields."""
        # Create unresolved conflict
        conflict = ConflictRecord(
            entity_stable_keys='["item:sword1", "item:sword2"]',
            conflict_type="name_collision",
            resolved=False,
            created_at=datetime.now(UTC),
        )
        in_memory_session.add(conflict)
        in_memory_session.commit()
        in_memory_session.refresh(conflict)

        assert conflict.resolved is False
        assert conflict.resolution_stable_key is None
        assert conflict.resolution_notes is None
        assert conflict.resolved_at is None

        # Resolve conflict
        conflict.resolved = True
        conflict.resolution_stable_key = "item:sword1"
        conflict.resolution_notes = "Chose item:sword1 as canonical"
        conflict.resolved_at = datetime.now(UTC)
        in_memory_session.add(conflict)
        in_memory_session.commit()
        in_memory_session.refresh(conflict)

        assert conflict.resolved is True
        assert conflict.resolution_stable_key == "item:sword1"
        assert conflict.resolution_notes == "Chose item:sword1 as canonical"
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
