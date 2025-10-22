"""Repository implementations for database access.

This package provides concrete repository implementations for all entity types,
building on the BaseRepository pattern for type-safe database operations.

Each repository:
- Inherits from BaseRepository[EntityType]
- Implements entity-specific CRUD operations
- Handles PascalCase ↔ snake_case conversion
- Provides common query methods (get_by_resource_name, etc.)

Available repositories:
- ItemRepository: Items and equipment
- SpellRepository: Spells and magical abilities
- SkillRepository: Combat skills and special abilities
- CharacterRepository: NPCs, creatures, and vendors
- QuestRepository: Quests and objectives
- FactionRepository: Factions and reputation
- ZoneRepository: Game zones and areas
- LootTableRepository: Loot drop tables
- SpawnPointRepository: Creature spawn points
- ItemStatsRepository: Item statistics by quality

Usage:
    >>> from erenshor.infrastructure.database.connection import DatabaseConnection
    >>> from erenshor.infrastructure.database.repositories import ItemRepository
    >>>
    >>> db = DatabaseConnection(Path("erenshor.sqlite"))
    >>> items = ItemRepository(db)
    >>> sword = items.get_by_resource_name("Iron Sword")
"""

from .characters import CharacterRepository
from .factions import FactionRepository
from .item_stats import ItemStatsRepository
from .items import ItemRepository
from .loot_tables import LootTableRepository
from .quests import QuestRepository
from .skills import SkillRepository
from .spawn_points import SpawnPointRepository
from .spells import SpellRepository
from .zones import ZoneRepository

__all__ = [
    "CharacterRepository",
    "FactionRepository",
    "ItemRepository",
    "ItemStatsRepository",
    "LootTableRepository",
    "QuestRepository",
    "SkillRepository",
    "SpawnPointRepository",
    "SpellRepository",
    "ZoneRepository",
]
