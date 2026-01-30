"""
Registry System.

Provides entity registration, lookup, and conflict detection.
Tracks entity relationships and enables cross-referencing between
different data types.

Modules:
- schema: Database schema definitions (EntityRecord)
- resource_names: Utilities for working with resource names as stable identifiers
- operations: Core registry CRUD operations and conflict detection
- resolver: Entity name resolution service (page titles, display names, image names)
- item_classifier: Item kind classification for category generation
"""

from erenshor.registry.item_classifier import ItemKind, classify_item_kind
from erenshor.registry.operations import (
    find_conflicts,
    get_entity,
    initialize_registry,
    list_entities,
    load_mapping_json,
    register_entity,
    validate_conflicts,
)
from erenshor.registry.resolver import RegistryResolver
from erenshor.registry.resource_names import (
    build_stable_key,
    extract_resource_name,
    validate_resource_name,
    validate_stable_key,
)
from erenshor.registry.schema import EntityRecord, EntityType

__all__ = [
    "EntityRecord",
    "EntityType",
    "ItemKind",
    "RegistryResolver",
    "build_stable_key",
    "classify_item_kind",
    "extract_resource_name",
    "find_conflicts",
    "get_entity",
    "initialize_registry",
    "list_entities",
    "load_mapping_json",
    "register_entity",
    "validate_conflicts",
    "validate_resource_name",
    "validate_stable_key",
]
