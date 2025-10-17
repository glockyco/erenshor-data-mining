"""Case conversion utilities for database field mapping.

This module provides utilities for converting between PascalCase (database columns)
and snake_case (Python entity fields).
"""

import re


def pascal_to_snake(name: str) -> str:
    """Convert PascalCase to snake_case.

    Args:
        name: PascalCase string (e.g., "ObjectName", "ResourceName").

    Returns:
        snake_case string (e.g., "object_name", "resource_name").

    Examples:
        >>> pascal_to_snake("ObjectName")
        'object_name'
        >>> pascal_to_snake("NPCName")
        'npc_name'
        >>> pascal_to_snake("BaseHP")
        'base_hp'
    """
    # Insert underscore before uppercase letters (except at start)
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    # Insert underscore before uppercase letters preceded by lowercase
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def snake_to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase.

    Args:
        name: snake_case string (e.g., "object_name", "resource_name").

    Returns:
        PascalCase string (e.g., "ObjectName", "ResourceName").

    Examples:
        >>> snake_to_pascal("object_name")
        'ObjectName'
        >>> snake_to_pascal("npc_name")
        'NpcName'
        >>> snake_to_pascal("base_hp")
        'BaseHp'
    """
    return "".join(word.capitalize() for word in name.split("_"))
