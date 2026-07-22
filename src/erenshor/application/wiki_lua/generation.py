"""Application service for local wiki Lua data module generation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from erenshor.application.wiki_lua.characters import (
    CharacterDataRepository,
    CharacterLootRepository,
    CharacterSpawnRepository,
    CharacterSpellRepository,
    write_characters_module,
)
from erenshor.application.wiki_lua.items import (
    ItemDataRepository as ItemModuleDataRepository,
)
from erenshor.application.wiki_lua.items import (
    ItemProvenanceCharacterRepository,
    ItemProvenanceItemRepository,
    ItemProvenanceQuestRepository,
    ItemProvenanceZoneRepository,
    build_item_sources_by_item,
    write_items_modules,
)
from erenshor.application.wiki_lua.link_catalog import (
    ClassDisplayNameService,
    FactionDataRepository,
    write_links_module,
)
from erenshor.application.wiki_lua.link_catalog import (
    ItemDataRepository as LinkCatalogItemDataRepository,
)
from erenshor.application.wiki_lua.quests import QuestDataRepository, write_quests_module
from erenshor.application.wiki_lua.skills import (
    SkillDataRepository as SkillModuleRepository,
)
from erenshor.application.wiki_lua.skills import (
    SkillRelationshipItemRepository,
    write_skills_module,
)
from erenshor.application.wiki_lua.spells import (
    SpellDataRepository,
    SpellRelationshipCharacterRepository,
    SpellRelationshipItemRepository,
    write_spells_module,
)
from erenshor.application.wiki_lua.stances import StanceDataRepository, write_stances_module
from erenshor.application.wiki_lua.validation import LuaValidationResult, validate_lua_module
from erenshor.application.wiki_lua.zones import ZoneDataRepository, write_zones_module


class WikiItemRepository(
    ItemModuleDataRepository,
    LinkCatalogItemDataRepository,
    ItemProvenanceItemRepository,
    Protocol,
):
    """Item repository contract needed by full Lua data generation."""


class WikiCharacterRepository(CharacterDataRepository, ItemProvenanceCharacterRepository, Protocol):
    """Character repository contract needed by full Lua data generation."""


class WikiQuestRepository(QuestDataRepository, ItemProvenanceQuestRepository, Protocol):
    """Quest repository contract needed by full Lua data generation."""


class WikiZoneRepository(ZoneDataRepository, ItemProvenanceZoneRepository, Protocol):
    """Zone repository contract needed for item provenance and zone modules."""


class WikiSpellItemRepository(
    WikiItemRepository, SpellRelationshipItemRepository, SkillRelationshipItemRepository, Protocol
):
    """Item repository contract needed by spell and skill Lua data generation."""


class WikiSpellCharacterRepository(WikiCharacterRepository, SpellRelationshipCharacterRepository, Protocol):
    """Character repository contract needed by spell Lua data generation."""


@dataclass(frozen=True)
class LuaDataModuleGenerationResult:
    """Files written and validators used during local Lua data generation."""

    written_paths: list[Path]
    validation_tools: dict[Path, str]


class SkillGenerationRepository(SkillModuleRepository, Protocol):
    """Skill repository methods needed by all generated Lua data modules."""


LuaValidator = Callable[[Path], LuaValidationResult]


class WikiFactionRepository(FactionDataRepository, Protocol):
    """Faction repository contract needed for semantic link catalog generation."""


_DATA_SUBDIR = ("Erenshor", "Data")

# Top-level data modules generation always writes, in deploy/validation order.
# Item shards under ``Erenshor/Data/Items`` are produced dynamically per item kind.
TOP_LEVEL_DATA_MODULES: tuple[str, ...] = (
    "Items.lua",
    "Characters.lua",
    "Links.lua",
    "Spells.lua",
    "Skills.lua",
    "Quests.lua",
    "Zones.lua",
    "Stances.lua",
)


def _data_dir(output_root: Path) -> Path:
    return output_root.joinpath(*_DATA_SUBDIR)


def planned_top_level_module_paths(output_root: Path) -> list[Path]:
    """Return the always-written top-level data module paths for an output root.

    This is the single source of truth shared by ``generate-lua`` dry-run output
    and generation, so the reported plan cannot drift from what is written.
    """
    data_dir = _data_dir(output_root)
    return [data_dir / name for name in TOP_LEVEL_DATA_MODULES]


def item_shard_dir(output_root: Path) -> Path:
    """Return the directory holding generated per-kind item shard modules."""
    return _data_dir(output_root) / "Items"


def _remove_stale_data_modules(output_root: Path, written_paths: list[Path]) -> None:
    """Delete previously generated data modules no longer produced by this run.

    Generation is the sole owner of ``Erenshor/Data``: a renamed shard scheme or a
    removed module must not leave orphan pages that later get deployed.
    """
    data_dir = _data_dir(output_root)
    if not data_dir.exists():
        return
    kept = {path.resolve() for path in written_paths}
    for path in data_dir.rglob("*.lua"):
        if path.is_file() and path.resolve() not in kept:
            path.unlink()
    for path in sorted(data_dir.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def generate_lua_data_modules(
    *,
    item_repo: WikiSpellItemRepository,
    character_repo: WikiSpellCharacterRepository,
    spawn_repo: CharacterSpawnRepository,
    loot_repo: CharacterLootRepository,
    spell_usage_repo: CharacterSpellRepository,
    spell_repo: SpellDataRepository,
    skill_repo: SkillGenerationRepository,
    stance_repo: StanceDataRepository,
    quest_repo: WikiQuestRepository,
    zone_repo: WikiZoneRepository,
    output_root: Path,
    faction_repo: WikiFactionRepository,
    class_display: ClassDisplayNameService,
    validate: LuaValidator = validate_lua_module,
) -> LuaDataModuleGenerationResult:
    """Generate and validate all currently supported Lua data modules."""
    items = item_repo.get_items_for_wiki_generation()
    item_sources_by_item = build_item_sources_by_item(items, item_repo, character_repo, quest_repo, zone_repo)
    class_display_names = {
        internal_name: class_display.get_display_name(internal_name)
        for internal_name in class_display.get_all_internal_names()
    }
    written_paths = [
        *write_items_modules(
            item_repo,
            output_root,
            sources_by_item=item_sources_by_item,
            class_display_names=class_display_names,
        ),
        write_characters_module(character_repo, spawn_repo, loot_repo, spell_usage_repo, output_root),
        write_links_module(
            item_repo,
            character_repo,
            quest_repo,
            zone_repo,
            spell_repo,
            skill_repo,
            stance_repo,
            faction_repo,
            class_display,
            output_root,
        ),
        write_spells_module(
            spell_repo,
            output_root,
            item_repo,
            character_repo,
            class_display_names=class_display_names,
        ),
        write_skills_module(skill_repo, output_root, item_repo),
        write_quests_module(quest_repo, output_root),
        write_zones_module(zone_repo, output_root),
        write_stances_module(stance_repo, output_root),
    ]
    _remove_stale_data_modules(output_root, written_paths)

    validation_tools: dict[Path, str] = {}
    for path in written_paths:
        validation = validate(path)
        validation_tools[path] = validation.tool

    return LuaDataModuleGenerationResult(written_paths=written_paths, validation_tools=validation_tools)
