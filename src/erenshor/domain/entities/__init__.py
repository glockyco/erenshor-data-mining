"""Domain entities for game data.

This module provides domain entity models representing game data structures
from the Unity export system. All entities use Pydantic for validation and
provide stable key generation for registry lookups.

Entity Types:
- Item: Equipment, consumables, quest items, crafting materials
- ItemStats: Item statistics by quality level (Normal, Blessed, Godly)
- Spell: Damage spells, buffs, debuffs, heals, crowd control
- Skill: Combat skills and special abilities
- Character: NPCs, creatures, vendors, quest givers
- Quest: Quest objectives, requirements, and rewards
- Faction: Reputation groups and organizations
- Zone: Map locations and geographic areas
- LootTable: Item drop data and probabilities
- SpawnPoint: Creature spawn locations and behavior

All entity models match the Unity export database schema and support
resource name-based stable key generation for cross-version tracking.
"""

from .base import BaseEntity
from .character import Character
from .faction import Faction
from .item import Item
from .item_stats import ItemStats
from .loot_table import LootTable
from .quest import Quest
from .skill import Skill
from .spawn_point import SpawnPoint
from .spell import Spell
from .zone import Zone

__all__ = [
    "BaseEntity",
    "Character",
    "Faction",
    "Item",
    "ItemStats",
    "LootTable",
    "Quest",
    "Skill",
    "SpawnPoint",
    "Spell",
    "Zone",
]
