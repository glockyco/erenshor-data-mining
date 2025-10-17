"""
Registry System.

Provides entity registration, lookup, and migration capabilities.
Tracks entity relationships and enables cross-referencing between
different data types.

Modules:
- schema: Database schema definitions (EntityRecord, MigrationRecord, ConflictRecord)
- resource_names: Utilities for working with resource names as stable identifiers
- core: Core registry functionality
- links: Entity linking and relationships
- migration: Migration tools and utilities
"""

from erenshor.registry.resource_names import (
    build_stable_key,
    extract_resource_name,
    normalize_resource_name,
    parse_stable_key,
    validate_resource_name,
    validate_stable_key,
)
from erenshor.registry.schema import ConflictRecord, EntityRecord, EntityType, MigrationRecord

__all__ = [
    "ConflictRecord",
    "EntityRecord",
    "EntityType",
    "MigrationRecord",
    "build_stable_key",
    "extract_resource_name",
    "normalize_resource_name",
    "parse_stable_key",
    "validate_resource_name",
    "validate_stable_key",
]
