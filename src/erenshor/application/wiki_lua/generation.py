"""Application service for local wiki Lua data module generation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from erenshor.application.wiki_lua.ability_links import (
    SkillDataRepository,
    StanceDataRepository,
    write_ability_links_module,
)
from erenshor.application.wiki_lua.characters import (
    CharacterDataRepository,
    CharacterLootRepository,
    CharacterSpawnRepository,
    CharacterSpellRepository,
    write_characters_module,
)
from erenshor.application.wiki_lua.items import ItemDataRepository, write_items_modules
from erenshor.application.wiki_lua.quests import QuestDataRepository, write_quests_module
from erenshor.application.wiki_lua.spells import SpellDataRepository, write_spells_module
from erenshor.application.wiki_lua.stances import write_stances_module
from erenshor.application.wiki_lua.validation import LuaValidationResult, validate_lua_module
from erenshor.application.wiki_lua.zones import ZoneDataRepository, write_zones_module


@dataclass(frozen=True)
class LuaDataModuleGenerationResult:
    """Files written and validators used during local Lua data generation."""

    written_paths: list[Path]
    validation_tools: dict[Path, str]


LuaValidator = Callable[[Path], LuaValidationResult]


def generate_lua_data_modules(
    *,
    item_repo: ItemDataRepository,
    character_repo: CharacterDataRepository,
    spawn_repo: CharacterSpawnRepository,
    loot_repo: CharacterLootRepository,
    spell_usage_repo: CharacterSpellRepository,
    spell_repo: SpellDataRepository,
    skill_repo: SkillDataRepository,
    stance_repo: StanceDataRepository,
    quest_repo: QuestDataRepository,
    zone_repo: ZoneDataRepository,
    output_root: Path,
    validate: LuaValidator = validate_lua_module,
) -> LuaDataModuleGenerationResult:
    """Generate and validate all currently supported Lua data modules."""
    written_paths = [
        *write_items_modules(item_repo, output_root),
        write_characters_module(character_repo, spawn_repo, loot_repo, spell_usage_repo, output_root),
        write_ability_links_module(spell_repo, skill_repo, stance_repo, output_root),
        write_spells_module(spell_repo, output_root),
        write_quests_module(quest_repo, output_root),
        write_zones_module(zone_repo, output_root),
        write_stances_module(stance_repo, output_root),
    ]
    validation_tools: dict[Path, str] = {}

    for path in written_paths:
        validation = validate(path)
        validation_tools[path] = validation.tool

    return LuaDataModuleGenerationResult(written_paths=written_paths, validation_tools=validation_tools)
