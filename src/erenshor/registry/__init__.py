"""
Registry System.

Provides entity registration, lookup, and migration capabilities.
Tracks entity relationships and enables cross-referencing between
different data types.

Modules:
- schema: Database schema definitions (EntityRecord, MigrationRecord, ConflictRecord)
- core: Core registry functionality
- links: Entity linking and relationships
- migration: Migration tools and utilities
"""

from erenshor.registry.schema import ConflictRecord, EntityRecord, EntityType, MigrationRecord

__all__ = [
    "ConflictRecord",
    "EntityRecord",
    "EntityType",
    "MigrationRecord",
]
