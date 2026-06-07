from __future__ import annotations

from typing import TYPE_CHECKING

from erenshor.domain.entities.character import Character
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.quest import Quest
from erenshor.domain.entities.skill import Skill
from erenshor.domain.entities.spell import Spell
from erenshor.domain.entities.stance import Stance
from erenshor.domain.entities.zone import Zone

if TYPE_CHECKING:
    from erenshor.domain.entities.item_stats import ItemStats
    from erenshor.domain.value_objects.crafting_recipe import CraftingRecipe
    from erenshor.domain.value_objects.faction import FactionModifier
    from erenshor.domain.value_objects.loot import ItemDropInfo, LootDropInfo
    from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
    from erenshor.domain.value_objects.wiki_link import AbilityLink, CharacterLink, ItemLink, QuestLink, StandardLink


class FakeItemRepository:
    def __init__(
        self,
        items: list[Item],
        stats: dict[str, list[ItemStats]],
        classes: dict[str, list[str]],
        recipes: dict[str, CraftingRecipe] | None = None,
        item_sources: dict[str, list[tuple[StandardLink, float]]] | None = None,
        items_requiring: dict[str, list[ItemLink]] | None = None,
        item_drops: dict[str, list[ItemDropInfo]] | None = None,
        spell_teaching_items: dict[str, list[ItemLink]] | None = None,
        skill_teaching_items: dict[str, list[ItemLink]] | None = None,
        spell_effect_items: dict[str, list[ItemLink]] | None = None,
        skill_effect_items: dict[str, list[ItemLink]] | None = None,
    ) -> None:
        self._items = items
        self._stats = stats
        self._classes = classes
        self._recipes = recipes or {}
        self._item_sources = item_sources or {}
        self._items_requiring = items_requiring or {}
        self._item_drops = item_drops or {}
        self._spell_teaching_items = spell_teaching_items or {}
        self._skill_teaching_items = skill_teaching_items or {}
        self._spell_effect_items = spell_effect_items or {}
        self._skill_effect_items = skill_effect_items or {}

    def get_items_for_wiki_generation(self) -> list[Item]:
        return self._items

    def get_item_stats(self, stable_key: str) -> list[ItemStats]:
        return self._stats.get(stable_key, [])

    def get_item_classes(self, stable_key: str) -> list[str]:
        return self._classes.get(stable_key, [])

    def get_crafting_recipe(self, stable_key: str) -> CraftingRecipe | None:
        return self._recipes.get(stable_key)

    def get_item_sources(self, item_stable_key: str) -> list[tuple[StandardLink, float]]:
        return self._item_sources.get(item_stable_key, [])

    def get_items_requiring_item(self, item_stable_key: str) -> list[ItemLink]:
        return self._items_requiring.get(item_stable_key, [])

    def get_item_drops(self, source_item_stable_key: str) -> list[ItemDropInfo]:
        return self._item_drops.get(source_item_stable_key, [])

    def get_obtainable_items_that_teach_spell(self, spell_stable_key: str) -> list[ItemLink]:
        return self._spell_teaching_items.get(spell_stable_key, [])

    def get_obtainable_items_that_teach_skill(self, skill_stable_key: str) -> list[ItemLink]:
        return self._skill_teaching_items.get(skill_stable_key, [])

    def get_items_with_spell_effect(self, spell_stable_key: str) -> list[ItemLink]:
        return self._spell_effect_items.get(spell_stable_key, [])

    def get_items_with_skill_effect(self, skill_stable_key: str) -> list[ItemLink]:
        return self._skill_effect_items.get(skill_stable_key, [])


class FakeCharacterRepository:
    def __init__(
        self,
        characters: list[Character],
        vendors: dict[str, list[CharacterLink]] | None = None,
        drops: dict[str, list[tuple[CharacterLink, float]]] | None = None,
        spell_users: dict[str, list[CharacterLink]] | None = None,
    ) -> None:
        self._characters = characters
        self._vendors = vendors or {}
        self._drops = drops or {}
        self._spell_users = spell_users or {}

    def get_characters_for_wiki_generation(self) -> list[Character]:
        return self._characters

    def get_vendors_selling_item(self, item_stable_key: str) -> list[CharacterLink]:
        return self._vendors.get(item_stable_key, [])

    def get_characters_dropping_item(self, item_stable_key: str) -> list[tuple[CharacterLink, float]]:
        return self._drops.get(item_stable_key, [])

    def get_characters_using_spell(self, spell_stable_key: str) -> list[CharacterLink]:
        return self._spell_users.get(spell_stable_key, [])


class FakeSpawnRepository:
    def __init__(self, spawns: dict[str, list[CharacterSpawnInfo]]) -> None:
        self._spawns = spawns

    def get_spawn_info_for_character(self, stable_key: str) -> list[CharacterSpawnInfo]:
        return self._spawns.get(stable_key, [])


class FakeLootRepository:
    def __init__(self, loot: dict[str, list[LootDropInfo]]) -> None:
        self._loot = loot

    def get_loot_for_character(self, stable_key: str) -> list[LootDropInfo]:
        return self._loot.get(stable_key, [])


class FakeSpellUsageRepository:
    def __init__(self, spells: dict[str, list[AbilityLink]]) -> None:
        self._spells = spells

    def get_spells_used_by_character(self, stable_key: str) -> list[AbilityLink]:
        return self._spells.get(stable_key, [])


class FakeSpellRepository:
    def __init__(self, spells: list[Spell], classes: dict[str, list[str]] | None = None) -> None:
        self._spells = spells
        self._classes = classes or {}

    def get_spells_for_wiki_generation(self) -> list[Spell]:
        return self._spells

    def get_spell_classes(self, stable_key: str) -> list[str]:
        return self._classes.get(stable_key, [])


class FakeSkillRepository:
    def __init__(self, skills: list[Skill], class_display_names: dict[str, str] | None = None) -> None:
        self._skills = skills
        self._class_display_names = class_display_names or {}

    def get_skills_for_wiki_generation(self) -> list[Skill]:
        return self._skills

    def get_class_display_names(self) -> dict[str, str]:
        return self._class_display_names


class FakeStanceRepository:
    def __init__(self, stances: list[Stance]) -> None:
        self._stances = stances

    def get_all(self) -> list[Stance]:
        return self._stances


class FakeQuestRepository:
    def __init__(
        self,
        quests: list[Quest],
        faction_changes: dict[str, list[FactionModifier]] | None = None,
        quest_rewards: dict[str, list[QuestLink]] | None = None,
        quest_requirements: dict[str, list[QuestLink]] | None = None,
    ) -> None:
        self._quests = quests
        self._faction_changes = faction_changes or {}
        self._quest_rewards = quest_rewards or {}
        self._quest_requirements = quest_requirements or {}

    def get_quests_for_wiki_generation(self) -> list[Quest]:
        return self._quests

    def get_faction_changes_for_quests(self, stable_keys: list[str]) -> dict[str, list[FactionModifier]]:
        return {stable_key: self._faction_changes.get(stable_key, []) for stable_key in stable_keys}

    def get_quests_rewarding_item(self, item_stable_key: str) -> list[QuestLink]:
        return self._quest_rewards.get(item_stable_key, [])

    def get_quests_requiring_item(self, item_stable_key: str) -> list[QuestLink]:
        return self._quest_requirements.get(item_stable_key, [])


class FakeZoneRepository:
    def __init__(self, zones: list[Zone], connections: dict[str, list[str]]) -> None:
        self._zones = zones
        self._connections = connections

    def get_all_zones(self) -> list[Zone]:
        return self._zones

    def get_zone_connections(self, scene_name: str) -> list[str]:
        return self._connections.get(scene_name, [])


def make_item(**overrides: object) -> Item:
    values = {
        "stable_key": "item:sword_of_flames",
        "item_name": "Sword of Flames",
        "display_name": "Sword of Flames",
        "wiki_page_name": "Sword of Flames",
        "image_name": "Sword of Flames",
        "lore": "Long prose should stay out of Lua data modules.",
        "required_slot": "Primary",
        "this_weapon_type": "Sword",
        "item_level": 12,
        "weapon_dly": 2.5,
        "item_value": 100,
        "sell_value": 25,
        "stackable": 0,
        "is_unique": 1,
    }
    values.update(overrides)
    return Item.model_validate(values)


def make_character(**overrides: object) -> Character:
    values = {
        "stable_key": "character:a_grizzly_bear",
        "object_name": "A Grizzly Bear",
        "npc_name": "A Grizzly Bear",
        "display_name": "A Grizzly Bear",
        "wiki_page_name": "A Grizzly Bear",
        "image_name": "A Grizzly Bear",
        "my_world_faction_display_name": "The Followers of Evil",
        "my_world_faction_wiki_page_name": "The Followers of Evil",
        "my_world_faction_stable_key": "faction:the_followers_of_evil",
        "is_common": 1,
        "is_rare": 0,
        "is_unique": 0,
        "is_friendly": 0,
        "level": 12,
        "boss_xp_multiplier": 1.0,
        "base_mana": 0,
        "base_str": 23,
        "base_end": 40,
        "base_dex": 5,
        "base_agi": 15,
        "base_int": 5,
        "base_wis": 5,
        "base_cha": 5,
        "effective_hp": 2340,
        "effective_ac": 180,
        "effective_min_mr": 6,
        "effective_max_mr": 14,
        "effective_min_pr": 6,
        "effective_max_pr": 14,
        "effective_min_er": 6,
        "effective_max_er": 14,
        "effective_min_vr": 6,
        "effective_max_vr": 14,
    }
    values.update(overrides)
    return Character.model_validate(values)


def make_spell(**overrides: object) -> Spell:
    values: dict[str, object] = {
        "stable_key": "spell:minor_lightning",
        "display_name": "Minor Lightning",
        "wiki_page_name": "Minor Lightning",
        "image_name": "Minor Lightning",
        "spell_name": "Minor Lightning",
    }
    values.update(overrides)
    return Spell.model_validate(values)


def make_skill(**overrides: object) -> Skill:
    values: dict[str, object] = {
        "stable_key": "skill:double_attack",
        "display_name": "Double Attack",
        "wiki_page_name": "Double Attack",
        "image_name": "Double Attack",
        "skill_name": "Double Attack",
    }
    values.update(overrides)
    return Skill.model_validate(values)


def make_stance(**overrides: object) -> Stance:
    values: dict[str, object] = {
        "stable_key": "stance:aggressive",
        "display_name": "Aggressive",
        "wiki_page_name": "Aggressive Stance",
        "image_name": "Aggressive",
    }
    values.update(overrides)
    return Stance.model_validate(values)


def make_quest(**overrides: object) -> Quest:
    values = {
        "stable_key": "quest:magical_sword",
        "display_name": "A Magical Sword in Port Azure",
        "wiki_page_name": "A Magical Sword in Port Azure",
        "image_name": "Magical Sword",
        "quest_name": "A Magical Sword in Port Azure",
        "repeatable": 0,
        "xp_on_complete": 450,
        "gold_on_complete": 12,
    }
    values.update(overrides)
    return Quest.model_validate(values)


def make_zone(**overrides: object) -> Zone:
    values = {
        "stable_key": "zone:PortAzure",
        "scene_name": "PortAzure",
        "zone_name": "Port Azure",
        "display_name": "Port Azure",
        "wiki_page_name": "Port Azure",
        "image_name": "Port Azure",
        "is_dungeon": 0,
        "is_wiki_generated": 1,
        "is_map_visible": 1,
    }
    values.update(overrides)
    return Zone.model_validate(values)
