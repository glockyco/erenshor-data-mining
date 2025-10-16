"""Database repositories - organized by entity type.

Provides backward-compatible imports for all repository functions.
Functions are now organized into focused modules:
- connection: Database engine management
- items: Item queries and item-related operations
- characters: Character/NPC queries and character-related operations
- spells: Spell and skill queries
- relationships: Cross-entity queries (factions, quests, drops, vendors)
- zones: Zone and location queries (fishing, mining)
"""

from erenshor.infrastructure.database.repositories.characters import (
    get_character_by_object_name,
    get_characters,
    get_characters_dropping_item,
    get_loot_for_character,
    get_spawnpoints_for_character,
    get_vendors_selling_item_by_name,
)
from erenshor.infrastructure.database.repositories.connection import (
    get_engine,
)
from erenshor.infrastructure.database.repositories.items import (
    get_auras,
    get_consumables_and_ability_books,
    get_crafting_recipe,
    get_fishable_item_names,
    get_item_stats,
    get_items,
    get_items_by_ids,
    get_items_producing_item,
    get_items_requiring_item,
    get_mining_item_names,
)
from erenshor.infrastructure.database.repositories.relationships import (
    get_faction_desc_by_ref,
    get_faction_ref_by_name,
    get_factions,
    get_factions_map,
    get_quest_by_dbname,
    get_quests_requiring_item,
    get_quests_rewarding_item,
)
from erenshor.infrastructure.database.repositories.spells import (
    get_items_that_teach_spell,
    get_items_with_effects_for_spell,
    get_skill_by_id,
    get_skills,
    get_spell_by_id,
    get_spells,
)
from erenshor.infrastructure.database.repositories.zones import (
    get_water_fishables,
    get_waters,
)

__all__ = [
    # Connection
    "get_engine",
    # Items
    "get_items",
    "get_item_stats",
    "get_consumables_and_ability_books",
    "get_auras",
    "get_items_by_ids",
    "get_crafting_recipe",
    "get_fishable_item_names",
    "get_mining_item_names",
    "get_items_producing_item",
    "get_items_requiring_item",
    # Characters
    "get_character_by_object_name",
    "get_characters",
    "get_loot_for_character",
    "get_spawnpoints_for_character",
    "get_characters_dropping_item",
    "get_vendors_selling_item_by_name",
    # Spells
    "get_spells",
    "get_spell_by_id",
    "get_skills",
    "get_skill_by_id",
    "get_items_with_effects_for_spell",
    "get_items_that_teach_spell",
    # Relationships
    "get_factions_map",
    "get_faction_ref_by_name",
    "get_faction_desc_by_ref",
    "get_factions",
    "get_quests_rewarding_item",
    "get_quests_requiring_item",
    "get_quest_by_dbname",
    # Zones
    "get_waters",
    "get_water_fishables",
]
