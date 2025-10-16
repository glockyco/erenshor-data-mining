"""Junction table audit service for database coverage validation.

This service detects junction tables in the database and compares them against
the registered junction metadata to identify missing registrations.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, text

from erenshor.infrastructure.database.junction_metadata import JUNCTION_METADATA

__all__ = ["JunctionAuditResult", "audit_junction_coverage"]


@dataclass
class JunctionAuditResult:
    """Result of junction table coverage audit.

    Attributes:
        db_tables: Set of junction table names found in database
        registered_tables: Set of junction table names registered in metadata
        missing: Set of junction tables in DB but not registered
        registered: Set of junction tables properly registered
    """

    db_tables: set[str]
    registered_tables: set[str]
    missing: set[str]
    registered: set[str]

    @property
    def is_complete(self) -> bool:
        """Check if all junction tables are registered."""
        return len(self.missing) == 0


def detect_junction_tables(engine: Engine) -> set[str]:
    """Detect potential junction tables in the database.

    Junction tables typically have:
    1. 2-4 columns total
    2. At least 1 column that references other tables (ending in Id or Guid)
    3. Table name often matches pattern: EntityName + FieldName
    4. Few or no other descriptive fields (Name, Desc, etc.)

    This includes both:
    - Entity-to-entity junctions (e.g., CharacterAttackSpells: CharacterId, SpellId)
    - Entity-to-value junctions (e.g., ItemClasses: ItemId, ClassName)

    Args:
        engine: SQLAlchemy engine connected to database

    Returns:
        Set of table names that appear to be junction tables
    """
    junction_tables: set[str] = set()

    with engine.connect() as conn:
        # Get all table names
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tables = [row[0] for row in result]

        for table_name in tables:
            # Skip special SQLite tables
            if table_name.startswith("sqlite_"):
                continue

            # Get table schema
            schema_result = conn.execute(text(f"PRAGMA table_info({table_name})"))
            columns = list(schema_result)

            # Skip if not in typical junction table column range
            if not (2 <= len(columns) <= 4):
                continue

            # Junction tables typically don't have auto-increment primary keys
            # (column[5] = 1 means it's a primary key in PRAGMA table_info)
            # Skip if any column is marked as primary key AND has INTEGER type
            has_auto_pk = any(
                col[5] == 1 and col[2].upper() == "INTEGER" for col in columns
            )
            if has_auto_pk:
                continue

            # Count columns that look like foreign keys (end with Id or Guid)
            fk_columns = [
                col[1]
                for col in columns
                if col[1].endswith("Id") or col[1].endswith("Guid")
            ]

            # Junction tables must have at least 1 FK-like column
            # With 2 columns total, if 1 is FK, it's likely a junction
            # With 3-4 columns, need at least 2 FKs to be confident
            if len(columns) == 2 and len(fk_columns) >= 1:
                junction_tables.add(table_name)
            elif len(columns) >= 3 and len(fk_columns) >= 2:
                junction_tables.add(table_name)

    return junction_tables


def get_registered_junctions() -> set[str]:
    """Get set of junction tables registered in metadata.

    Returns:
        Set of registered junction table names
    """
    return set(JUNCTION_METADATA.keys())


def audit_junction_coverage(engine: Engine) -> JunctionAuditResult:
    """Audit junction table coverage by comparing DB tables to registered metadata.

    Args:
        engine: SQLAlchemy engine connected to database

    Returns:
        JunctionAuditResult with comparison details
    """
    db_tables = detect_junction_tables(engine)
    registered_tables = get_registered_junctions()

    missing = db_tables - registered_tables
    registered = db_tables & registered_tables

    return JunctionAuditResult(
        db_tables=db_tables,
        registered_tables=registered_tables,
        missing=missing,
        registered=registered,
    )
