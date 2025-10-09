"""Unit tests for JunctionEnricher - metadata-driven junction table loading.

Tests the generic enricher with various aggregation strategies:
- COMMA_SEPARATED: String concatenation with separator
- LIST_OF_STRINGS: List of string values
- LIST_OF_OBJECTS: List of dataclass instances
- CUSTOM: Custom aggregator functions

Also tests error handling, fail-fast behavior, and edge cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from erenshor.infrastructure.database.junction_metadata import (
    JunctionAggregation,
    JunctionMeta,
)
from erenshor.infrastructure.database.junction_enricher import JunctionEnricher


@dataclass
class SampleObject:
    """Sample dataclass for LIST_OF_OBJECTS aggregation."""

    value1: str
    value2: int


class SampleEntity(BaseModel):
    """Sample entity model."""

    Id: str
    Name: str
    Classes: str | None = None
    Tags: list[str] | None = None
    Details: list[SampleObject] | None = None


def create_test_db() -> Engine:
    """Create an in-memory test database with sample junction tables."""
    engine = create_engine("sqlite:///:memory:")

    with engine.connect() as conn:
        # Create main entity table
        conn.execute(
            text(
                """
            CREATE TABLE TestEntities (
                Id VARCHAR PRIMARY KEY,
                Name VARCHAR,
                Classes VARCHAR
            )
        """
            )
        )

        # Create junction table for COMMA_SEPARATED test
        conn.execute(
            text(
                """
            CREATE TABLE EntityClasses (
                EntityId VARCHAR,
                ClassName VARCHAR
            )
        """
            )
        )

        # Create junction table for LIST_OF_STRINGS test
        conn.execute(
            text(
                """
            CREATE TABLE EntityTags (
                EntityId VARCHAR,
                TagName VARCHAR
            )
        """
            )
        )

        # Create junction table for LIST_OF_OBJECTS test
        conn.execute(
            text(
                """
            CREATE TABLE EntityDetails (
                EntityId VARCHAR,
                Value1 VARCHAR,
                Value2 INTEGER
            )
        """
            )
        )

        # Insert test data
        conn.execute(
            text(
                """
            INSERT INTO TestEntities VALUES
                ('e1', 'Entity One', 'OldClass'),
                ('e2', 'Entity Two', ''),
                ('e3', 'Entity Three', '')
        """
            )
        )

        # Insert junction data - EntityClasses (COMMA_SEPARATED)
        conn.execute(
            text(
                """
            INSERT INTO EntityClasses VALUES
                ('e1', 'Warrior'),
                ('e1', 'Mage'),
                ('e1', 'Rogue'),
                ('e2', 'Priest')
        """
            )
        )

        # Insert junction data - EntityTags (LIST_OF_STRINGS)
        conn.execute(
            text(
                """
            INSERT INTO EntityTags VALUES
                ('e1', 'Common'),
                ('e1', 'Strong'),
                ('e2', 'Rare')
        """
            )
        )

        # Insert junction data - EntityDetails (LIST_OF_OBJECTS)
        conn.execute(
            text(
                """
            INSERT INTO EntityDetails VALUES
                ('e1', 'Detail A', 100),
                ('e1', 'Detail B', 200),
                ('e2', 'Detail C', 300)
        """
            )
        )

        conn.commit()

    return engine


def test_comma_separated_aggregation():
    """Test COMMA_SEPARATED aggregation - most common case."""
    engine = create_test_db()
    try:
        # Create test entities
        entities = [
            SampleEntity(Id="e1", Name="Entity One"),
            SampleEntity(Id="e2", Name="Entity Two"),
            SampleEntity(Id="e3", Name="Entity Three"),
        ]

        # Create metadata for EntityClasses junction
        meta = JunctionMeta(
            table="EntityClasses",
            entity_id_field="Id",
            entity_id_column="EntityId",
            target_field="Classes",
            related_columns=["ClassName"],
            aggregation=JunctionAggregation.COMMA_SEPARATED,
            order_by="ClassName",  # Alphabetical
            separator=", ",
        )

        # Enrich entities
        enricher = JunctionEnricher(engine)
        enricher._enrich_single_junction(entities, meta)

        # Verify results
        assert entities[0].Classes == "Mage, Rogue, Warrior"  # Alphabetical order
        assert entities[1].Classes == "Priest"
        assert entities[2].Classes is None  # No junction rows
    finally:
        engine.dispose()


def test_list_of_strings_aggregation():
    """Test LIST_OF_STRINGS aggregation."""
    engine = create_test_db()
    try:
        # Create test entities
        entities = [
            SampleEntity(Id="e1", Name="Entity One"),
            SampleEntity(Id="e2", Name="Entity Two"),
            SampleEntity(Id="e3", Name="Entity Three"),
        ]

        # Create metadata for EntityTags junction
        meta = JunctionMeta(
            table="EntityTags",
            entity_id_field="Id",
            entity_id_column="EntityId",
            target_field="Tags",
            related_columns=["TagName"],
            aggregation=JunctionAggregation.LIST_OF_STRINGS,
            order_by="TagName",
        )

        # Enrich entities
        enricher = JunctionEnricher(engine)
        enricher._enrich_single_junction(entities, meta)

        # Verify results
        assert entities[0].Tags == ["Common", "Strong"]
        assert entities[1].Tags == ["Rare"]
        assert entities[2].Tags is None  # No junction data
    finally:
        engine.dispose()


def test_list_of_objects_aggregation():
    """Test LIST_OF_OBJECTS aggregation with dataclass conversion."""
    engine = create_test_db()
    try:
        # Create test entities
        entities = [
            SampleEntity(Id="e1", Name="Entity One"),
            SampleEntity(Id="e2", Name="Entity Two"),
            SampleEntity(Id="e3", Name="Entity Three"),
        ]

        # Create metadata for EntityDetails junction
        meta = JunctionMeta(
            table="EntityDetails",
            entity_id_field="Id",
            entity_id_column="EntityId",
            target_field="Details",
            related_columns=["Value1", "Value2"],
            aggregation=JunctionAggregation.LIST_OF_OBJECTS,
            dataclass_type=SampleObject,
            order_by="Value2",  # Order by numeric value
        )

        # Enrich entities
        enricher = JunctionEnricher(engine)
        enricher._enrich_single_junction(entities, meta)

        # Verify results
        assert len(entities[0].Details) == 2
        assert entities[0].Details[0].value1 == "Detail A"
        assert entities[0].Details[0].value2 == 100
        assert entities[0].Details[1].value1 == "Detail B"
        assert entities[0].Details[1].value2 == 200

        assert len(entities[1].Details) == 1
        assert entities[1].Details[0].value1 == "Detail C"
        assert entities[1].Details[0].value2 == 300

        assert entities[2].Details is None  # No junction data
    finally:
        engine.dispose()


def test_custom_aggregation():
    """Test CUSTOM aggregation with custom function."""
    engine = create_test_db()
    try:
        # Create test entities
        entities = [
            SampleEntity(Id="e1", Name="Entity One"),
            SampleEntity(Id="e2", Name="Entity Two"),
        ]

        # Custom aggregator: Count of rows
        def count_aggregator(rows: list[dict[str, Any]]) -> str:
            return f"Count: {len(rows)}"

        # Create metadata with custom aggregator
        meta = JunctionMeta(
            table="EntityClasses",
            entity_id_field="Id",
            entity_id_column="EntityId",
            target_field="Classes",
            related_columns=["ClassName"],
            aggregation=JunctionAggregation.CUSTOM,
            custom_aggregator=count_aggregator,
        )

        # Enrich entities
        enricher = JunctionEnricher(engine)
        enricher._enrich_single_junction(entities, meta)

        # Verify results
        assert entities[0].Classes == "Count: 3"  # e1 has 3 classes
        assert entities[1].Classes == "Count: 1"  # e2 has 1 class
    finally:
        engine.dispose()


def test_empty_entity_list():
    """Test that enriching empty list doesn't error."""
    engine = create_test_db()
    try:
        entities: list[SampleEntity] = []

        meta = JunctionMeta(
            table="EntityClasses",
            entity_id_field="Id",
            entity_id_column="EntityId",
            target_field="Classes",
            related_columns=["ClassName"],
            aggregation=JunctionAggregation.COMMA_SEPARATED,
        )

        enricher = JunctionEnricher(engine)
        enricher._enrich_single_junction(entities, meta)

        # Should not raise, list stays empty
        assert len(entities) == 0
    finally:
        engine.dispose()


def test_fail_fast_on_missing_table():
    """Test fail-fast behavior when junction table doesn't exist."""
    engine = create_test_db()
    try:
        # Create entities
        entities = [
            SampleEntity(Id="e1", Name="Entity One", Classes="OriginalClass1"),
            SampleEntity(Id="e2", Name="Entity Two", Classes="OriginalClass2"),
        ]

        # Enrich with non-existent table
        # "NonExistentTable" is not registered in JUNCTION_METADATA,
        # so the enricher will raise KeyError immediately
        enricher = JunctionEnricher(engine)

        with pytest.raises(
            KeyError, match="Junction table 'NonExistentTable' not found"
        ):
            enricher.enrich(entities, ["NonExistentTable"])
    finally:
        engine.dispose()


def test_custom_separator():
    """Test COMMA_SEPARATED with custom separator."""
    engine = create_test_db()
    try:
        entities = [SampleEntity(Id="e1", Name="Entity One")]

        meta = JunctionMeta(
            table="EntityClasses",
            entity_id_field="Id",
            entity_id_column="EntityId",
            target_field="Classes",
            related_columns=["ClassName"],
            aggregation=JunctionAggregation.COMMA_SEPARATED,
            order_by="ClassName",
            separator=" | ",  # Custom separator
        )

        enricher = JunctionEnricher(engine)
        enricher._enrich_single_junction(entities, meta)

        assert entities[0].Classes == "Mage | Rogue | Warrior"
    finally:
        engine.dispose()


def test_filter_clause():
    """Test filtering junction rows with filter_clause."""
    engine = create_test_db()
    try:
        # Add a filtered junction table
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                CREATE TABLE EntityClassesFiltered (
                    EntityId VARCHAR,
                    ClassName VARCHAR,
                    IsActive INTEGER
                )
            """
                )
            )
            conn.execute(
                text(
                    """
                INSERT INTO EntityClassesFiltered VALUES
                    ('e1', 'ActiveClass', 1),
                    ('e1', 'InactiveClass', 0),
                    ('e1', 'AnotherActive', 1)
            """
                )
            )
            conn.commit()

        entities = [SampleEntity(Id="e1", Name="Entity One")]

        meta = JunctionMeta(
            table="EntityClassesFiltered",
            entity_id_field="Id",
            entity_id_column="EntityId",
            target_field="Classes",
            related_columns=["ClassName"],
            aggregation=JunctionAggregation.COMMA_SEPARATED,
            order_by="ClassName",
            filter_clause="IsActive = 1",  # Only active classes
            separator=", ",
        )

        enricher = JunctionEnricher(engine)
        enricher._enrich_single_junction(entities, meta)

        # Should only include active classes
        assert entities[0].Classes == "ActiveClass, AnotherActive"
    finally:
        engine.dispose()


def test_batch_enrichment_multiple_junctions():
    """Test enriching with multiple junction tables at once."""
    engine = create_test_db()
    try:
        entities = [
            SampleEntity(Id="e1", Name="Entity One"),
            SampleEntity(Id="e2", Name="Entity Two"),
        ]

        # Create multiple metadata entries
        meta_classes = JunctionMeta(
            table="EntityClasses",
            entity_id_field="Id",
            entity_id_column="EntityId",
            target_field="Classes",
            related_columns=["ClassName"],
            aggregation=JunctionAggregation.COMMA_SEPARATED,
            order_by="ClassName",
            separator=", ",
        )

        meta_tags = JunctionMeta(
            table="EntityTags",
            entity_id_field="Id",
            entity_id_column="EntityId",
            target_field="Tags",
            related_columns=["TagName"],
            aggregation=JunctionAggregation.LIST_OF_STRINGS,
            order_by="TagName",
        )

        # Enrich with both junction tables
        enricher = JunctionEnricher(engine)
        enricher._enrich_single_junction(entities, meta_classes)
        enricher._enrich_single_junction(entities, meta_tags)

        # Verify both fields are populated
        assert entities[0].Classes == "Mage, Rogue, Warrior"
        assert entities[0].Tags == ["Common", "Strong"]
        assert entities[1].Classes == "Priest"
        assert entities[1].Tags == ["Rare"]
    finally:
        engine.dispose()


def test_list_of_objects_missing_dataclass_type():
    """Test that LIST_OF_OBJECTS without dataclass_type raises error."""
    engine = create_test_db()
    try:
        # Missing dataclass_type for LIST_OF_OBJECTS
        # This should fail validation in __post_init__
        try:
            JunctionMeta(
                table="EntityDetails",
                entity_id_field="Id",
                entity_id_column="EntityId",
                target_field="Details",
                related_columns=["Value1", "Value2"],
                aggregation=JunctionAggregation.LIST_OF_OBJECTS,
                # dataclass_type=None  # Missing!
            )
            assert False, "Should have raised ValueError during construction"
        except ValueError as e:
            assert "dataclass_type" in str(e)
    finally:
        engine.dispose()


def test_custom_aggregation_missing_function():
    """Test that CUSTOM without custom_aggregator raises error."""
    engine = create_test_db()
    try:
        # Missing custom_aggregator for CUSTOM
        # This should fail validation in __post_init__
        try:
            JunctionMeta(
                table="EntityClasses",
                entity_id_field="Id",
                entity_id_column="EntityId",
                target_field="Classes",
                related_columns=["ClassName"],
                aggregation=JunctionAggregation.CUSTOM,
                # custom_aggregator=None  # Missing!
            )
            assert False, "Should have raised ValueError during construction"
        except ValueError as e:
            assert "custom_aggregator" in str(e)
    finally:
        engine.dispose()
