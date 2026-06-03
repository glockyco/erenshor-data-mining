from __future__ import annotations

from typing import TYPE_CHECKING

from erenshor.domain.entities.character import Character
from erenshor.domain.entities.item import Item

if TYPE_CHECKING:
    from erenshor.domain.entities.item_stats import ItemStats
    from erenshor.domain.value_objects.loot import LootDropInfo
    from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
    from erenshor.domain.value_objects.wiki_link import AbilityLink


class FakeItemRepository:
    def __init__(self, items: list[Item], stats: dict[str, list[ItemStats]], classes: dict[str, list[str]]) -> None:
        self._items = items
        self._stats = stats
        self._classes = classes

    def get_items_for_wiki_generation(self) -> list[Item]:
        return self._items

    def get_item_stats(self, stable_key: str) -> list[ItemStats]:
        return self._stats.get(stable_key, [])

    def get_item_classes(self, stable_key: str) -> list[str]:
        return self._classes.get(stable_key, [])


class FakeCharacterRepository:
    def __init__(self, characters: list[Character]) -> None:
        self._characters = characters

    def get_characters_for_wiki_generation(self) -> list[Character]:
        return self._characters


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
