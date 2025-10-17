"""Resource name utilities for stable entity identification.

This module provides utilities for working with resource names as stable identifiers
across game versions. Different entity types use different fields as their stable
identifier (e.g., Items use "ResourceName", Characters use "ObjectName", Quests use
"DBName", Factions use "REFNAME").

Stable Key Format:
    The registry uses a consistent key format: {entity_type}:{resource_name}
    Examples:
    - "item:iron_sword"
    - "character:goblin_warrior"
    - "quest:main_quest_01"
    - "faction:merchant_guild"

Key Concepts:
- Resource Name: The stable identifier field from game data (varies by entity type)
- Stable Key: Combination of entity type and resource name in format "type:name"
- Normalization: Consistent formatting (lowercase, trimmed whitespace)
- Validation: Ensures keys are well-formed and usable

The stable key format enables:
- Consistent entity tracking across game versions
- Type-safe lookups and relationships
- Clear separation between different entity types
- Easy parsing and validation
"""

from typing import Any

from .schema import EntityType


def normalize_resource_name(resource_name: str) -> str:
    """Normalize a resource name to consistent format.

    Normalization Rules:
    - Convert to lowercase
    - Strip leading/trailing whitespace
    - Replace multiple consecutive spaces with single space
    - Preserve underscores and other special characters

    IMPORTANT: This normalization is LOSSY. The original case and exact whitespace
    formatting cannot be reconstructed from the normalized form. This is intentional
    to enable case-insensitive and whitespace-tolerant lookups. The display_name
    field in EntityRecord preserves the original formatting for display purposes.

    Args:
        resource_name: The resource name to normalize

    Returns:
        Normalized resource name with consistent formatting

    Examples:
        >>> normalize_resource_name("  Iron Sword  ")
        "iron sword"
        >>> normalize_resource_name("GoblinWarrior")
        "goblinwarrior"
        >>> normalize_resource_name("main_quest_01")
        "main_quest_01"
        >>> normalize_resource_name("Sword  of   Flames")
        "sword of flames"
    """
    # Strip whitespace and convert to lowercase
    normalized = resource_name.strip().lower()

    # Replace multiple spaces with single space
    while "  " in normalized:
        normalized = normalized.replace("  ", " ")

    return normalized


def validate_resource_name(resource_name: str) -> bool:
    """Validate that a resource name is valid.

    Validation Rules:
    - Non-empty after normalization
    - No colon characters (conflicts with stable key format)
    - Length between 1 and 255 characters

    Args:
        resource_name: The resource name to validate

    Returns:
        True if the resource name is valid, False otherwise

    Examples:
        >>> validate_resource_name("iron_sword")
        True
        >>> validate_resource_name("")
        False
        >>> validate_resource_name("valid:name")  # Contains colon
        False
        >>> validate_resource_name("a" * 256)  # Too long
        False
        >>> validate_resource_name("  ")  # Empty after normalization
        False
    """
    # Normalize first to check actual content
    normalized = normalize_resource_name(resource_name)

    # Check if empty after normalization
    if not normalized:
        return False

    # Check for colon (conflicts with stable key format)
    if ":" in normalized:
        return False

    # Check length constraints
    return not len(normalized) > 255


def build_stable_key(entity_type: EntityType, resource_name: str) -> str:
    """Build a stable key from entity type and resource name.

    The stable key format is: {entity_type.value}:{resource_name}

    The resource_name is automatically normalized to ensure consistency.
    Inputs are validated - empty resource names will raise ValueError.

    Args:
        entity_type: The type of entity (item, spell, character, etc.)
        resource_name: The resource identifier from game data

    Returns:
        Stable key in format "entity_type:resource_name"

    Raises:
        ValueError: If resource_name is empty or invalid

    Examples:
        >>> build_stable_key(EntityType.ITEM, "iron_sword")
        "item:iron_sword"
        >>> build_stable_key(EntityType.CHARACTER, "Goblin Warrior")
        "character:goblin warrior"
        >>> build_stable_key(EntityType.QUEST, "MainQuest_01")
        "quest:mainquest_01"
        >>> build_stable_key(EntityType.ITEM, "")
        Traceback (most recent call last):
            ...
        ValueError: Resource name cannot be empty
    """
    # Normalize resource name
    normalized = normalize_resource_name(resource_name)

    # Validate resource name
    if not normalized:
        raise ValueError("Resource name cannot be empty")

    if not validate_resource_name(normalized):
        raise ValueError(f"Invalid resource name: {resource_name!r}")

    # Build stable key
    return f"{entity_type.value}:{normalized}"


def parse_stable_key(key: str) -> tuple[EntityType, str]:
    """Parse a stable key into entity type and resource name.

    Splits the key on the first colon and validates both parts.

    Args:
        key: The stable key to parse (format: "entity_type:resource_name")

    Returns:
        Tuple of (EntityType, resource_name)

    Raises:
        ValueError: If key format is invalid or entity type is unknown

    Examples:
        >>> parse_stable_key("item:iron_sword")
        (EntityType.ITEM, "iron_sword")
        >>> parse_stable_key("character:goblin_warrior")
        (EntityType.CHARACTER, "goblin_warrior")
        >>> parse_stable_key("quest:main_quest_01")
        (EntityType.QUEST, "main_quest_01")
        >>> parse_stable_key("invalid_key")
        Traceback (most recent call last):
            ...
        ValueError: Invalid stable key format: 'invalid_key' (must contain ':')
        >>> parse_stable_key("unknown_type:some_name")
        Traceback (most recent call last):
            ...
        ValueError: Unknown entity type: 'unknown_type'
    """
    # Validate key contains colon
    if ":" not in key:
        raise ValueError(f"Invalid stable key format: {key!r} (must contain ':')")

    # Split on first colon only
    entity_type_str, resource_name = key.split(":", 1)

    # Validate entity type
    try:
        entity_type = EntityType(entity_type_str)
    except ValueError as e:
        raise ValueError(f"Unknown entity type: {entity_type_str!r}") from e

    # Return parsed components
    return entity_type, resource_name


def extract_resource_name(entity_type: EntityType, entity_data: dict[str, Any]) -> str:
    """Extract resource name from entity data based on entity type.

    Different entity types use different fields as their stable identifier:
    - Items, Spells, Skills: Use "ResourceName" field
    - Characters: Use "ObjectName" field
    - Quests: Use "DBName" field
    - Factions: Use "REFNAME" field
    - Other types: Try "ResourceName", fallback to "Name", or return empty string

    The extracted value is automatically normalized for consistency.

    Args:
        entity_type: The type of entity being processed
        entity_data: Dictionary containing entity data from game export

    Returns:
        Normalized resource name extracted from appropriate field

    Raises:
        KeyError: If required field is missing for strict entity types

    Examples:
        >>> extract_resource_name(EntityType.ITEM, {"ResourceName": "IronSword"})
        "ironsword"
        >>> extract_resource_name(EntityType.CHARACTER, {"ObjectName": "Goblin Warrior"})
        "goblin warrior"
        >>> extract_resource_name(EntityType.QUEST, {"DBName": "MainQuest_01"})
        "mainquest_01"
        >>> extract_resource_name(EntityType.FACTION, {"REFNAME": "MerchantGuild"})
        "merchantguild"
        >>> extract_resource_name(EntityType.LOCATION, {"Name": "Elderwood"})
        "elderwood"
        >>> extract_resource_name(EntityType.ITEM, {"Name": "Sword"})
        Traceback (most recent call last):
            ...
        KeyError: "Missing required field 'ResourceName' for entity type 'item'"
    """
    # Define field mappings for each entity type
    field_name: str | None = None

    if entity_type in (EntityType.ITEM, EntityType.SPELL, EntityType.SKILL):
        # Items, spells, and skills use ResourceName
        field_name = "ResourceName"
        if field_name not in entity_data:
            raise KeyError(f"Missing required field {field_name!r} for entity type {entity_type.value!r}")
        value = entity_data[field_name]

    elif entity_type == EntityType.CHARACTER:
        # Characters use ObjectName
        field_name = "ObjectName"
        if field_name not in entity_data:
            raise KeyError(f"Missing required field {field_name!r} for entity type {entity_type.value!r}")
        value = entity_data[field_name]

    elif entity_type == EntityType.QUEST:
        # Quests use DBName
        field_name = "DBName"
        if field_name not in entity_data:
            raise KeyError(f"Missing required field {field_name!r} for entity type {entity_type.value!r}")
        value = entity_data[field_name]

    elif entity_type == EntityType.FACTION:
        # Factions use REFNAME
        field_name = "REFNAME"
        if field_name not in entity_data:
            raise KeyError(f"Missing required field {field_name!r} for entity type {entity_type.value!r}")
        value = entity_data[field_name]

    else:
        # Other entity types: try ResourceName, fallback to Name, or empty string
        value = entity_data.get("ResourceName", entity_data.get("Name", ""))

    # Normalize and return
    return normalize_resource_name(str(value))


def validate_stable_key(key: str) -> bool:
    """Validate that a stable key has correct format.

    Validation checks:
    - Contains exactly one colon separator
    - Entity type part is a valid EntityType value
    - Resource name part passes validate_resource_name()

    Args:
        key: The stable key to validate

    Returns:
        True if the key is valid, False otherwise

    Examples:
        >>> validate_stable_key("item:iron_sword")
        True
        >>> validate_stable_key("character:goblin_warrior")
        True
        >>> validate_stable_key("invalid_key")  # No colon
        False
        >>> validate_stable_key("unknown_type:some_name")  # Invalid entity type
        False
        >>> validate_stable_key("item:")  # Empty resource name
        False
        >>> validate_stable_key("item:valid:name")  # Too many colons
        False
    """
    # Check for colon separator
    if ":" not in key:
        return False

    # Check for multiple colons (split should produce exactly 2 parts)
    parts = key.split(":")
    if len(parts) != 2:
        return False

    entity_type_str, resource_name = parts

    # Validate entity type
    try:
        EntityType(entity_type_str)
    except ValueError:
        return False

    # Validate resource name
    return validate_resource_name(resource_name)
