"""Entity type value object."""

from __future__ import annotations

from enum import Enum

__all__ = ["EntityType"]


class EntityType(Enum):
    """Types of database entities that can be mapped to wiki pages."""

    ITEM = "item"
    CHARACTER = "character"
    SPELL = "spell"
    SKILL = "skill"
    QUEST = "quest"
    FACTION = "faction"
    OVERVIEW = "overview"  # entity without DB representation
