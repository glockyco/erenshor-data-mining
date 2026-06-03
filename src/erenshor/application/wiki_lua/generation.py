"""Application service for local wiki Lua data module generation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from erenshor.application.wiki_lua.characters import (
    CharacterDataRepository,
    CharacterLootRepository,
    CharacterSpawnRepository,
    CharacterSpellRepository,
    write_characters_module,
)
from erenshor.application.wiki_lua.items import ItemDataRepository, write_items_module
from erenshor.application.wiki_lua.validation import LuaValidationResult, validate_lua_module


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
    spell_repo: CharacterSpellRepository,
    output_root: Path,
    validate: LuaValidator = validate_lua_module,
) -> LuaDataModuleGenerationResult:
    """Generate and validate all currently supported Lua data modules."""
    written_paths = [
        write_items_module(item_repo, output_root),
        write_characters_module(character_repo, spawn_repo, loot_repo, spell_repo, output_root),
    ]
    validation_tools: dict[Path, str] = {}

    for path in written_paths:
        validation = validate(path)
        validation_tools[path] = validation.tool

    return LuaDataModuleGenerationResult(written_paths=written_paths, validation_tools=validation_tools)
