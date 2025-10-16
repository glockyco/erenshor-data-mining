"""Generic junction table enricher for batch-loading related data.

This module provides a generic, metadata-driven system for enriching entities
with data from junction tables. Instead of writing custom batch-fetch code for
each junction table, we declare the structure once in metadata and use this
enricher to automatically populate entity fields.

Design Philosophy:
- Generic: One implementation handles all junction tables
- Batch-efficient: Single query per junction table, regardless of entity count
- Type-safe: Preserves entity types, validates metadata
- Fail-fast: Raises exceptions on any error (no silent fallbacks)
- DRY: Eliminates repetitive batch-fetch logic in repositories

Example Usage:
    >>> from erenshor.infrastructure.database.junction_enricher import JunctionEnricher
    >>> enricher = JunctionEnricher(engine)
    >>> items = [DbItem(...), DbItem(...)]
    >>> enricher.enrich(items, ["ItemClasses"])
    >>> # items[0].Classes now contains "Arcanist, Druid" from ItemClasses table

Architecture:
    Infrastructure:   junction_metadata.py (metadata registry) + junction_enricher.py (queries database)
    Repositories:     Use enricher instead of manual batch-fetch code
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError, OperationalError

from erenshor.domain.exceptions import JunctionEnrichmentError
from erenshor.infrastructure.database.junction_metadata import (
    JUNCTION_METADATA,
    JunctionAggregation,
    JunctionMeta,
    get_junction_meta,
)

logger = logging.getLogger(__name__)


class EnrichableEntity(Protocol):
    """Protocol for entities that can be enriched by JunctionEnricher."""

    def model_copy(self, *, update: dict[str, Any]) -> EnrichableEntity: ...


T = TypeVar("T", bound=BaseModel)

# SQLite has a limit of 999 variables per query
# Use conservative batch size to avoid SQL parameter limits
MAX_BATCH_SIZE = 500


class JunctionEnricher:
    """Enriches entities with junction table data using metadata-driven queries.

    This class provides generic batch-loading for junction tables. Given a list
    of entities and junction table names, it:
    1. Reads metadata to understand junction table structure
    2. Builds efficient batch queries to fetch all related data
    3. Groups results by entity ID
    4. Aggregates data according to metadata rules
    5. Populates entity fields with aggregated values

    The enricher handles all junction tables generically - no custom code needed
    for new junction tables, just add metadata to the registry.
    """

    def __init__(self, engine: Engine) -> None:
        """Initialize enricher with database engine.

        Args:
            engine: SQLAlchemy database engine for executing queries
        """
        self.engine = engine

    def enrich(self, entities: list[T], junction_names: list[str]) -> None:
        """Enrich entities with data from junction tables.

        Modifies entities in-place, populating their fields from junction tables.
        All errors are raised immediately - no silent fallbacks.

        Args:
            entities: List of entity objects to enrich (e.g., list[DbItem])
            junction_names: Junction table names to load (e.g., ["ItemClasses"])

        Raises:
            KeyError: If junction metadata not registered
            JunctionEnrichmentError: If database query fails or table doesn't exist
            ValueError: If metadata configuration is invalid (programming bug)
            AttributeError: If entity missing expected field (programming bug)

        Example:
            >>> items = get_items(engine)
            >>> enricher.enrich(items, ["ItemClasses"])
            >>> # Items now have Classes from ItemClasses junction table
            >>> # Raises exception if junction table missing or query fails
        """
        if not entities:
            return

        for junction_name in junction_names:
            try:
                meta = get_junction_meta(junction_name)
                self._enrich_single_junction(entities, meta)
            except KeyError as e:
                # Junction metadata not registered - this is a configuration error
                available = ", ".join(sorted(JUNCTION_METADATA.keys()))
                raise KeyError(
                    f"Junction table '{junction_name}' not found in metadata registry. "
                    f"Available tables: {available}"
                ) from e
            except (DatabaseError, OperationalError) as e:
                # Database errors: table doesn't exist, invalid SQL, connection issues
                raise JunctionEnrichmentError(
                    f"Failed to enrich from junction table '{junction_name}': {e}"
                ) from e
            except (ValueError, AttributeError):
                # ValueError: Invalid metadata configuration (programming bug)
                # AttributeError: Entity missing expected field (programming bug)
                # These always raise - they indicate bugs, not data issues
                raise

    def _enrich_single_junction(self, entities: list[T], meta: JunctionMeta) -> None:
        """Enrich entities from a single junction table.

        Args:
            entities: Entities to enrich
            meta: JunctionMeta describing table structure
        """
        # Extract entity IDs
        entity_ids = [getattr(e, meta.entity_id_field) for e in entities]
        if not entity_ids:
            return

        # Query in batches if needed to avoid SQL parameter limits
        if len(entity_ids) > MAX_BATCH_SIZE:
            rows = []
            for i in range(0, len(entity_ids), MAX_BATCH_SIZE):
                batch = entity_ids[i : i + MAX_BATCH_SIZE]
                rows.extend(self._query_junction_table(batch, meta))
        else:
            rows = self._query_junction_table(entity_ids, meta)

        # Group rows by entity ID
        grouped = self._group_by_entity_id(rows, meta)

        # Aggregate and populate entity fields
        for i, entity in enumerate(entities):
            entity_id = getattr(entity, meta.entity_id_field)
            entity_rows = grouped.get(entity_id, [])
            aggregated_value = self._aggregate(entity_rows, meta)
            # Use model_copy for type-safe field updates (preserves Pydantic validation)
            entities[i] = entity.model_copy(
                update={meta.target_field: aggregated_value}
            )

    def _query_junction_table(
        self, entity_ids: list[Any], meta: JunctionMeta
    ) -> list[dict[str, Any]]:
        """Query junction table for entity IDs.

        WARNING: Table and column names from metadata are interpolated into SQL.
        Only use trusted metadata from the registry. Never use untrusted input.

        Args:
            entity_ids: List of entity ID values to query
            meta: JunctionMeta with table structure

        Returns:
            List of row dicts with entity_id_column + related_columns
        """
        # Build SELECT clause
        columns = [meta.entity_id_column] + meta.related_columns
        select_clause = ", ".join(columns)

        # Build WHERE clause with IN (...)
        # Use named parameters for safety
        placeholders = ", ".join([f":id{i}" for i in range(len(entity_ids))])
        params = {f"id{i}": entity_ids[i] for i in range(len(entity_ids))}

        # Build optional clauses
        where_clause = f"{meta.entity_id_column} IN ({placeholders})"
        if meta.filter_clause:
            where_clause += f" AND ({meta.filter_clause})"

        order_clause = ""
        if meta.order_by:
            # Always order by entity ID first for efficient grouping
            order_clause = f"ORDER BY {meta.entity_id_column}, {meta.order_by}"
        else:
            order_clause = f"ORDER BY {meta.entity_id_column}"

        # Build complete query
        query = f"""
            SELECT {select_clause}
            FROM {meta.table}
            WHERE {where_clause}
            {order_clause}
        """

        # Execute query
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params)
            return [dict(row._mapping) for row in result]

    def _group_by_entity_id(
        self, rows: list[dict[str, Any]], meta: JunctionMeta
    ) -> dict[Any, list[dict[str, Any]]]:
        """Group junction rows by entity ID.

        Args:
            rows: All junction table rows
            meta: JunctionMeta with entity_id_column

        Returns:
            Dict mapping entity_id -> list of rows for that entity
        """
        grouped: dict[Any, list[dict[str, Any]]] = {}
        for row in rows:
            entity_id = row[meta.entity_id_column]
            if entity_id not in grouped:
                grouped[entity_id] = []
            grouped[entity_id].append(row)
        return grouped

    def _aggregate(self, rows: list[dict[str, Any]], meta: JunctionMeta) -> Any:
        """Aggregate junction rows into single value per metadata rules.

        Args:
            rows: All junction rows for one entity
            meta: JunctionMeta with aggregation strategy

        Returns:
            Aggregated value to assign to entity field
        """
        if not rows:
            return self._get_empty_value(meta)

        # Dispatch to appropriate aggregation strategy
        if meta.aggregation == JunctionAggregation.COMMA_SEPARATED:
            return self._aggregate_comma_separated(rows, meta)
        elif meta.aggregation == JunctionAggregation.LIST_OF_STRINGS:
            return self._aggregate_list_of_strings(rows, meta)
        elif meta.aggregation == JunctionAggregation.LIST_OF_OBJECTS:
            return self._aggregate_list_of_objects(rows, meta)
        elif meta.aggregation == JunctionAggregation.CUSTOM:
            return self._aggregate_custom(rows, meta)
        else:
            raise ValueError(f"Unknown aggregation type: {meta.aggregation}")

    def _get_empty_value(self, meta: JunctionMeta) -> Any:
        """Get appropriate empty value based on aggregation type.

        Returns None for all aggregation types. Entity fields are Optional[T],
        so None indicates no junction table data exists for this entity.

        Args:
            meta: JunctionMeta with aggregation strategy

        Returns:
            None - indicating no data in junction table for this entity
        """
        return None

    def _aggregate_comma_separated(
        self, rows: list[dict[str, Any]], meta: JunctionMeta
    ) -> str:
        """Aggregate rows into comma-separated string.

        Args:
            rows: Junction table rows
            meta: Metadata with separator configuration

        Returns:
            Comma-separated string of values
        """
        first_col = meta.related_columns[0]
        values = [str(row[first_col]) for row in rows if row.get(first_col)]
        return meta.separator.join(values)

    def _aggregate_list_of_strings(
        self, rows: list[dict[str, Any]], meta: JunctionMeta
    ) -> list[str]:
        """Aggregate rows into list of strings.

        Args:
            rows: Junction table rows
            meta: Metadata with column configuration

        Returns:
            List of string values
        """
        first_col = meta.related_columns[0]
        return [str(row[first_col]) for row in rows if row.get(first_col)]

    def _aggregate_list_of_objects(
        self, rows: list[dict[str, Any]], meta: JunctionMeta
    ) -> list[Any]:
        """Aggregate rows into list of dataclass instances.

        Args:
            rows: Junction table rows
            meta: Metadata with dataclass type and optional column mapping

        Returns:
            List of dataclass instances

        Raises:
            ValueError: If dataclass_type not provided
        """
        if not meta.dataclass_type:
            raise ValueError(
                f"LIST_OF_OBJECTS aggregation requires dataclass_type, "
                f"but none provided for table {meta.table}"
            )

        objects = []
        for row in rows:
            # Use explicit column-to-field mapping if provided, else lowercase columns
            if meta.column_to_field_map:
                obj_data = {
                    meta.column_to_field_map[col]: row[col]
                    for col in meta.related_columns
                }
            else:
                obj_data = {col.lower(): row[col] for col in meta.related_columns}
            objects.append(meta.dataclass_type(**obj_data))
        return objects

    def _aggregate_custom(self, rows: list[dict[str, Any]], meta: JunctionMeta) -> Any:
        """Aggregate rows using custom aggregator function.

        Args:
            rows: Junction table rows
            meta: Metadata with custom aggregator

        Returns:
            Result from custom aggregator function

        Raises:
            ValueError: If custom_aggregator not provided
        """
        if not meta.custom_aggregator:
            raise ValueError(
                f"CUSTOM aggregation requires custom_aggregator function, "
                f"but none provided for table {meta.table}"
            )
        return meta.custom_aggregator(rows)


__all__ = ["JunctionEnricher"]
