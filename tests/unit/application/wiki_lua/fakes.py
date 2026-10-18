from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Literal

from erenshor.application.processor.npc_spawn import SpawnConstants
from erenshor.domain.entities.character import Character
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.quest import Quest
from erenshor.domain.entities.skill import Skill
from erenshor.domain.entities.spell import Spell
from erenshor.domain.entities.stance import Stance
from erenshor.domain.entities.zone import Zone
from erenshor.domain.value_objects.item_provenance import (
    ItemAcquisition,
    ItemDisposition,
    ItemUse,
    conditions_satisfiable,
)
from erenshor.domain.value_objects.wiki_link import AbilityLink

if TYPE_CHECKING:
    from erenshor.domain.entities.item_stats import ItemStats
    from erenshor.domain.value_objects.crafting_recipe import CraftingRecipe
    from erenshor.domain.value_objects.faction import FactionModifier
    from erenshor.domain.value_objects.progression import ProgressionNode, ProgressionWay
    from erenshor.domain.value_objects.vendor_stock import VendorStockEntry
    from erenshor.domain.value_objects.wiki_link import CharacterLink, ItemLink


@dataclass
class FakeProgressionRepository:
    nodes: tuple[ProgressionNode, ...]
    ways: dict[str, tuple[ProgressionWay, ...]]

    def get_nodes(self) -> tuple[ProgressionNode, ...]:
        return self.nodes

    def get_ways(self, key: str) -> tuple[ProgressionWay, ...]:
        return self.ways.get(key, ())


class FakeItemProvenanceRepository:
    def __init__(
        self,
        item_keys: list[str],
        acquisitions: list[ItemAcquisition] | None = None,
        uses: list[ItemUse] | None = None,
        dispositions: list[ItemDisposition] | None = None,
        common_world_characters: frozenset[str] = frozenset(),
    ) -> None:
        self._acquisitions = acquisitions or []
        self._uses = uses or []
        self._common_world_characters = common_world_characters
        self._dispositions = {
            row.item_stable_key: row
            for row in (
                dispositions
                if dispositions is not None
                else [ItemDisposition(key, "current", current_pages=(key.removeprefix("item:"),)) for key in item_keys]
            )
        }

    def get_acquisitions(self, item_key: str) -> list[ItemAcquisition]:
        return [row for row in self._acquisitions if row.item_stable_key == item_key]

    def get_character_drop_acquisitions(self, actual_copy_keys: Iterable[str]) -> list[ItemAcquisition]:
        copies = set(actual_copy_keys)
        return [
            row for row in self._acquisitions if row.kind == "character_drop" and row.source_copy_stable_key in copies
        ]

    def get_uses(self, item_key: str) -> list[ItemUse]:
        return [row for row in self._uses if row.item_stable_key == item_key]

    def get_uses_targeting(self, target_key: str) -> list[ItemUse]:
        return [row for row in self._uses if row.target_stable_key == target_key]

    def get_disposition(self, item_key: str) -> ItemDisposition | None:
        return self._dispositions.get(item_key)

    def get_player_access(self, item_key: str) -> Literal["verified_player", "unconfirmed_player", "no_verified_path"]:
        disposition = self.get_disposition(item_key)
        if disposition is None or disposition.disposition != "current":
            return "no_verified_path"
        for access in ("verified_player", "unconfirmed_player"):
            if any(
                fact.player_access_state == access
                and fact.probability_stage == "final_acquisition"
                and not (fact.probability_max is not None and fact.probability_max <= 0)
                and conditions_satisfiable(fact.conditions)
                and (
                    not fact.locations
                    or any(conditions_satisfiable(fact.conditions + location.conditions) for location in fact.locations)
                )
                for fact in self.get_acquisitions(item_key)
            ):
                return access
        return "no_verified_path"

    def iter_acquisitions(self) -> Iterator[ItemAcquisition]:
        return iter(self._acquisitions)

    def iter_uses(self) -> Iterator[ItemUse]:
        return iter(self._uses)

    def iter_dispositions(self) -> Iterator[ItemDisposition]:
        return iter(sorted(self._dispositions.values(), key=lambda row: row.item_stable_key))

    def get_common_world_character_keys(self) -> frozenset[str]:
        return self._common_world_characters


class FakeItemRepository:
    def __init__(
        self,
        items: list[Item],
        stats: dict[str, list[ItemStats]],
        classes: dict[str, list[str]],
        recipes: dict[str, CraftingRecipe] | None = None,
        spell_teaching_items: dict[str, list[ItemLink]] | None = None,
        skill_teaching_items: dict[str, list[ItemLink]] | None = None,
        spell_effect_items: dict[str, list[ItemLink]] | None = None,
        skill_effect_items: dict[str, list[ItemLink]] | None = None,
        catalog_items: list[Item] | None = None,
    ) -> None:
        self._items = items
        self._catalog_items = items if catalog_items is None else catalog_items
        self._stats = stats
        self._classes = classes
        self._recipes = recipes or {}
        self._spell_teaching_items = spell_teaching_items or {}
        self._skill_teaching_items = skill_teaching_items or {}
        self._spell_effect_items = spell_effect_items or {}
        self._skill_effect_items = skill_effect_items or {}

    def get_items_for_wiki_generation(self) -> list[Item]:
        return self._items

    def get_items_for_link_catalog(self) -> list[Item]:
        return self._catalog_items

    def get_item_stats(self, stable_key: str) -> list[ItemStats]:
        return self._stats.get(stable_key, [])

    def get_item_classes(self, stable_key: str) -> list[str]:
        return self._classes.get(stable_key, [])

    def get_crafting_recipe(self, stable_key: str) -> CraftingRecipe | None:
        return self._recipes.get(stable_key)

    def get_item_renders(self, stable_key: str) -> dict[str | None, str]:
        return {}

    def get_obtainable_items_that_teach_spell(self, spell_stable_key: str) -> list[ItemLink]:
        return self._spell_teaching_items.get(spell_stable_key, [])

    def get_obtainable_items_that_teach_skill(self, skill_stable_key: str) -> list[ItemLink]:
        return self._skill_teaching_items.get(skill_stable_key, [])

    def get_classes_that_can_learn_spell(self, spell_stable_key: str) -> list[str]:
        classes: set[str] = set()
        for item in self._items:
            if item.teach_spell_stable_key == spell_stable_key:
                classes.update(self._classes.get(item.stable_key, []))
        return sorted(classes)

    def get_items_with_spell_effect(self, spell_stable_key: str) -> list[ItemLink]:
        return self._spell_effect_items.get(spell_stable_key, [])

    def get_items_with_skill_effect(self, skill_stable_key: str) -> list[ItemLink]:
        return self._skill_effect_items.get(skill_stable_key, [])


class FakeCharacterRepository:
    def __init__(
        self,
        characters: list[Character],
        spell_users: dict[str, list[CharacterLink]] | None = None,
        vendor_stock: list[VendorStockEntry] | None = None,
        members: dict[str, list[Character]] | None = None,
        placements: list[dict[str, object]] | None = None,
        abilities: dict[str, list[dict[str, object]]] | None = None,
        catalog: dict[str, dict[str, object]] | None = None,
        classes: list[dict[str, object]] | None = None,
        summoners: list[dict[str, object]] | None = None,
    ) -> None:
        self._characters = characters
        self._spell_users = spell_users or {}
        self._vendor_stock = vendor_stock or []
        self._members = (
            members if members is not None else {character.stable_key: [character] for character in characters}
        )
        self._placements = placements
        self._abilities = abilities or {}
        self._catalog = catalog or {}
        self._character_classes = classes or []
        self._summoners = summoners or []

    def get_characters_for_wiki_generation(self) -> list[Character]:
        return self._characters

    def get_character_data_members(self, stable_key: str) -> list[Character]:
        return self._members[stable_key]

    def get_character_data_abilities(self, stable_key: str) -> list[dict[str, object]]:
        return self._abilities.get(stable_key, [])

    def get_character_placements(self) -> list[dict[str, object]]:
        if self._placements is not None:
            return self._placements
        return [
            {
                "representative_stable_key": representative,
                "character_stable_key": member.stable_key,
                "placement_kind": "unplaced",
                "can_be_damaged": bool(member.can_be_damaged),
                "initial_invulnerable": bool(member.invulnerable),
                "stop_quests": [],
                "gates": [],
                "entries": [],
                "damage_releases": [],
            }
            for representative, members in self._members.items()
            for member in members
        ]

    def get_character_data_catalog(self) -> dict[str, dict[str, object]]:
        return {
            member.stable_key: {"name": member.display_name, "page": member.wiki_page_name}
            for members in self._members.values()
            for member in members
        } | self._catalog

    def get_character_data_classes(self) -> list[dict[str, object]]:
        return self._character_classes

    def get_character_data_spawn_constants(self) -> SpawnConstants:
        return SpawnConstants(1, 1.3, 1.75, 1.1, 1.1)

    def get_character_data_summoners(self) -> list[dict[str, object]]:
        return self._summoners

    def get_characters_using_spell(self, spell_stable_key: str) -> list[CharacterLink]:
        return self._spell_users.get(spell_stable_key, [])

    def get_vendor_stock(self) -> list[VendorStockEntry]:
        return self._vendor_stock

    def get_zone_roster_spawns(self) -> list[dict[str, object]]:
        return []

    def get_game_board_spawns(self) -> list[dict[str, object]]:
        return []


class FakeSpellRepository:
    def __init__(self, spells: list[Spell], classes: dict[str, list[str]] | None = None) -> None:
        self._spells = spells
        self._classes = classes or {}

    def get_spells_for_wiki_generation(self) -> list[Spell]:
        return self._spells

    def get_spell_classes(self, stable_key: str) -> list[str]:
        return self._classes.get(stable_key, [])

    def get_class_ability_teachers(self) -> list[dict[str, object]]:
        return []


class FakeSkillRepository:
    def __init__(self, skills: list[Skill], class_display_names: dict[str, str] | None = None) -> None:
        self._skills = skills
        self._class_display_names = class_display_names or {}

    def get_skills_for_wiki_generation(self) -> list[Skill]:
        return self._skills

    def get_class_display_names(self) -> dict[str, str]:
        return self._class_display_names

    def get_skills_using_stance(self, stance_stable_key: str) -> list[AbilityLink]:
        return [
            AbilityLink(
                page_title=skill.wiki_page_name,
                display_name=skill.display_name or skill.skill_name or skill.stable_key,
                image_name=skill.image_name,
                stable_key=skill.stable_key,
            )
            for skill in sorted(self._skills, key=lambda row: (row.display_name or "").casefold())
            if skill.stance_to_use_stable_key == stance_stable_key
        ]


class FakeFactionRepository:
    def __init__(self, factions: list[object] | None = None) -> None:
        self._factions = factions if factions is not None else [make_faction()]

    def get_factions_for_wiki_generation(self) -> list[object]:
        return self._factions


class FakeClassDisplayService:
    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self._mapping = mapping if mapping is not None else {"Windblade": "Windblade"}

    def get_all_internal_names(self) -> list[str]:
        return list(self._mapping)

    def get_display_name(self, class_name: str) -> str:
        return self._mapping[class_name]


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
    ) -> None:
        self._quests = quests
        self._faction_changes = faction_changes or {}

    def get_quest_panel_rows(self) -> dict[str, list[dict[str, object]]]:
        return {}

    def get_quests_for_wiki_generation(self) -> list[Quest]:
        return self._quests

    def get_faction_changes_for_quests(self, stable_keys: list[str]) -> dict[str, list[FactionModifier]]:
        return {stable_key: self._faction_changes.get(stable_key, []) for stable_key in stable_keys}


class FakeZoneRepository:
    def __init__(
        self,
        zones: list[Zone],
        connections: dict[str, list[str]],
    ) -> None:
        self._zones = zones
        self._connections = connections

    def get_all_zones(self) -> list[Zone]:
        return self._zones

    def get_zone_connections(self, scene_name: str) -> list[str]:
        return self._connections.get(scene_name, [])

    def get_zone_overview_spawns(self) -> list[dict[str, object]]:
        return []

    def get_zone_overview_connections(self) -> list[dict[str, object]]:
        return []


def make_faction(**overrides: object) -> object:
    values: dict[str, object] = {
        "stable_key": "faction:the_followers_of_evil",
        "display_name": "The Followers of Evil",
        "wiki_page_name": "The Followers of Evil",
        "image_name": "The Followers of Evil",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_item(**overrides: object) -> Item:
    values = {
        "stable_key": "item:sword_of_flames",
        "item_name": "Sword of Flames",
        "item_db_index": 1,
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
        "encounter_tier": "enemy",
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
        "zone_type": "Outdoor",
        "raid_capable": False,
        "use_zone_as_temp_bind": "",
        "is_wiki_generated": 1,
        "is_map_visible": 1,
    }
    values.update(overrides)
    return Zone.model_validate(values)
