"""Application service for local wiki Lua data module generation."""

from __future__ import annotations

import shutil
import tempfile
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.build import BuildDataRepository, write_build_module
from erenshor.application.wiki_lua.character_placements import build_character_locations
from erenshor.application.wiki_lua.characters import (
    CharacterDataRepository as CharacterModuleDataRepository,
)
from erenshor.application.wiki_lua.characters import build_character_records, write_characters_modules
from erenshor.application.wiki_lua.class_abilities import ClassAbilityRepository, write_class_abilities_module
from erenshor.application.wiki_lua.entity_lifecycle import write_entity_lifecycle_module
from erenshor.application.wiki_lua.game_board import GameBoardRepository, write_game_board_module
from erenshor.application.wiki_lua.items import write_items_modules
from erenshor.application.wiki_lua.items_v2 import CompleteItemDataRepository, write_items_v2_modules
from erenshor.application.wiki_lua.link_catalog import (
    CharacterDataRepository as LinkCatalogCharacterRepository,
)
from erenshor.application.wiki_lua.link_catalog import (
    ClassDisplayNameService,
    FactionDataRepository,
    build_link_catalog_entries,
    write_links_module,
)
from erenshor.application.wiki_lua.link_catalog import (
    ItemDataRepository as LinkCatalogItemDataRepository,
)
from erenshor.application.wiki_lua.link_catalog import (
    QuestDataRepository as LinkCatalogQuestRepository,
)
from erenshor.application.wiki_lua.link_catalog import (
    ZoneDataRepository as LinkCatalogZoneRepository,
)
from erenshor.application.wiki_lua.progression import ProgressionDataRepository, write_progression_module
from erenshor.application.wiki_lua.quests import QuestPanelRepository, write_quests_module
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
from erenshor.application.wiki_lua.stance_relations import StanceActivationRepository, write_stance_relations_module
from erenshor.application.wiki_lua.stances import StanceDataRepository, write_stances_module
from erenshor.application.wiki_lua.treasure import TreasureDataRepository, write_treasure_guardians_module
from erenshor.application.wiki_lua.validation import LuaValidationResult, validate_lua_module
from erenshor.application.wiki_lua.vendor_stock import VendorStockRepository, write_vendor_stock_module
from erenshor.application.wiki_lua.world_drops import write_world_drops_module
from erenshor.application.wiki_lua.zone_rosters import ZoneRosterRepository, write_zone_rosters_module
from erenshor.domain.value_objects.item_provenance import fact_to_dict

if TYPE_CHECKING:
    from erenshor.application.processor.npc_spawn import SpawnConstants
    from erenshor.domain.value_objects.item_provenance import ItemAcquisition
    from erenshor.infrastructure.content_lifecycle import ContentLifecycle
    from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository


class WikiItemRepository(
    LinkCatalogItemDataRepository,
    CompleteItemDataRepository,
    Protocol,
):
    """Item repository contract needed by full Lua data generation."""


class WikiCharacterRepository(
    LinkCatalogCharacterRepository,
    CharacterModuleDataRepository,
    VendorStockRepository,
    ZoneRosterRepository,
    GameBoardRepository,
    Protocol,
):
    """Character metadata and exact copy relationships needed by generated wiki data."""

    def get_character_placements(self) -> list[dict[str, object]]: ...

    def get_character_data_catalog(self) -> dict[str, dict[str, object]]: ...

    def get_character_data_classes(self) -> list[dict[str, object]]: ...

    def get_character_data_spawn_constants(self) -> SpawnConstants: ...

    def get_character_data_summoners(self) -> list[dict[str, object]]: ...


class WikiQuestRepository(LinkCatalogQuestRepository, QuestPanelRepository, Protocol):
    """Quest repository contract for links and quest panels."""


class WikiZoneRepository(LinkCatalogZoneRepository, Protocol):
    """Zone repository contract for semantic links."""


class WikiSpellItemRepository(
    WikiItemRepository,
    SpellRelationshipItemRepository,
    SkillRelationshipItemRepository,
    Protocol,
):
    """Item repository contract needed by spell and skill Lua data generation."""


class WikiSpellCharacterRepository(WikiCharacterRepository, SpellRelationshipCharacterRepository, Protocol):
    """Character repository contract needed by spell Lua data generation."""


@dataclass(frozen=True)
class LuaDataModuleGenerationResult:
    """Generated Lua modules, validators, and offline provenance sidecars."""

    written_paths: list[Path]
    validation_tools: dict[Path, str]
    manifest_paths: tuple[Path, ...] = ()


class SkillGenerationRepository(SkillModuleRepository, StanceActivationRepository, Protocol):
    """Skill repository methods needed by all generated Lua data modules."""


LuaValidator = Callable[[Path], LuaValidationResult]


class WikiSpellRepository(SpellDataRepository, ClassAbilityRepository, Protocol):
    """Spell repository contract including class learning relationships."""


class WikiFactionRepository(FactionDataRepository, Protocol):
    """Faction repository contract needed for semantic link catalog generation."""


_DATA_SUBDIR = ("Erenshor", "Data")

# Top-level data modules generation always writes, in deploy/validation order.
# Entity shards are discovered during generation rather than included in the dry-run plan.
TOP_LEVEL_DATA_MODULES: tuple[str, ...] = (
    "Items.lua",
    "ItemsV2.lua",
    "Characters.lua",
    "Links.lua",
    "Spells.lua",
    "Skills.lua",
    "Stances.lua",
    "StanceRelations.lua",
    "EntityLifecycle.lua",
    "Build.lua",
    "TreasureGuardians.lua",
    "VendorStock.lua",
    "WorldDrops.lua",
    "ZoneRosters.lua",
    "ClassAbilities.lua",
    "Quests.lua",
    "Progression.lua",
    "GameBoard.lua",
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


def build_character_generation_records(
    *,
    character_repo: WikiCharacterRepository,
    provenance_repo: ItemProvenanceRepository,
    treasure_repo: TreasureDataRepository,
    catalog: Mapping[str, Mapping[str, object]],
    class_labels: Mapping[str, Mapping[str, object]],
    constants: SpawnConstants,
    mitigations: Mapping[str, float],
    build: Mapping[str, object],
    lifecycle: ContentLifecycle,
    summoned_by_character: Mapping[str, Sequence[Mapping[str, object]]],
    common_world_characters: frozenset[str],
) -> dict[str, dict[str, object]]:
    """Compose character records from exact shared placements and canonical item facts."""
    resolved_catalog: dict[str, Mapping[str, object]] = dict(catalog)
    for disposition in provenance_repo.iter_dispositions():
        key = disposition.item_stable_key
        if key in resolved_catalog:
            resolved_catalog[key] = dict(resolved_catalog[key]) | {"disposition": fact_to_dict(disposition)}
    placements = character_repo.get_character_placements()
    copy_to_representative: dict[str, str] = {}
    for placement in placements:
        copy = str(placement["character_stable_key"])
        placement_representative = str(placement["representative_stable_key"])
        previous = copy_to_representative.setdefault(copy, placement_representative)
        if previous != placement_representative:
            raise ValueError(f"{copy}: character copy belongs to multiple representatives")
    acquisitions: defaultdict[str, list[ItemAcquisition]] = defaultdict(list)
    for fact in provenance_repo.get_character_drop_acquisitions(copy_to_representative):
        if fact.source_copy_stable_key is None:
            raise ValueError(f"{fact.acquisition_key}: character drop lacks its exact source copy")
        representative = copy_to_representative.get(fact.source_copy_stable_key)
        if representative is not None:
            acquisitions[representative].append(fact)
    notices: dict[str, dict[str, object]] = {}
    for page in lifecycle.pages.values():
        representative = copy_to_representative.get(page.stable_key or "")
        if representative is None:
            continue
        notice: dict[str, object] = {"state": page.state, "thing": page.thing}
        for field, value in (("update", page.update), ("date", page.date), ("url", page.patch_notes_url)):
            if value is not None:
                notice[field] = value
        if page.chat:
            notice["chat"] = True
        if representative in notices and notices[representative] != notice:
            raise ValueError(f"{representative}: conflicting reviewed character lifecycle notices")
        notices[representative] = notice
    guardians = frozenset(
        copy_to_representative.get(guardian.stable_key, guardian.stable_key)
        for guardian in treasure_repo.get_treasure_guardians()
    )
    summoners: defaultdict[str, list[Mapping[str, object]]] = defaultdict(list)
    for copy, relations in summoned_by_character.items():
        representative = copy_to_representative.get(copy)
        if representative is not None:
            summoners[representative].extend(dict(relation) | {"memberKey": copy} for relation in relations)
    return build_character_records(
        character_repo,
        locations_by_character=build_character_locations(placements, resolved_catalog),
        acquisitions_by_character=acquisitions,
        catalog=resolved_catalog,
        class_labels=class_labels,
        constants=constants,
        mitigations=mitigations,
        build=build,
        guardian_keys=guardians,
        summoned_by_character=summoners,
        common_world_characters=frozenset(copy_to_representative.get(key, key) for key in common_world_characters),
        lifecycle_by_character=notices,
    )


def generate_lua_data_modules(
    *,
    build_repo: BuildDataRepository,
    item_repo: WikiSpellItemRepository,
    character_repo: WikiSpellCharacterRepository,
    spell_repo: WikiSpellRepository,
    skill_repo: SkillGenerationRepository,
    stance_repo: StanceDataRepository,
    quest_repo: WikiQuestRepository,
    zone_repo: WikiZoneRepository,
    provenance_repo: ItemProvenanceRepository,
    treasure_repo: TreasureDataRepository,
    progression_repo: ProgressionDataRepository,
    output_root: Path,
    faction_repo: WikiFactionRepository,
    class_display: ClassDisplayNameService,
    max_page_bytes: int,
    lifecycle: ContentLifecycle,
    validate: LuaValidator = validate_lua_module,
) -> LuaDataModuleGenerationResult:
    """Generate Lua modules after checking that every page fits the wiki limit."""
    items = item_repo.get_items_for_wiki_generation()
    class_display_names = {
        internal_name: class_display.get_display_name(internal_name)
        for internal_name in class_display.get_all_internal_names()
    }
    link_entries = build_link_catalog_entries(
        items=item_repo.get_items_for_link_catalog(),
        characters=character_repo.get_characters_for_wiki_generation(),
        quests=quest_repo.get_quests_for_wiki_generation(),
        zones=zone_repo.get_all_zones(),
        spells=spell_repo.get_spells_for_wiki_generation(),
        skills=skill_repo.get_skills_for_wiki_generation(),
        stances=stance_repo.get_all(),
        factions=faction_repo.get_factions_for_wiki_generation(),
        class_display=class_display,
    )
    known_keys = frozenset(entry.key for entry in link_entries)
    game_build_id, published_at = build_repo.get_build_metadata()
    build = {"gameBuildId": game_build_id, "publishedAt": published_at}
    character_catalog = character_repo.get_character_data_catalog() | {
        entry.key: entry.primitive() for entry in link_entries
    }
    class_pages = {entry.name: entry.page for entry in link_entries if entry.kind == "class"}
    class_labels: dict[str, dict[str, object]] = {}
    mitigations: dict[str, float] = {}
    for row in character_repo.get_character_data_classes():
        resource = str(row["resource_name"])
        class_name = str(row["class_name"])
        label: dict[str, object] = {"name": row["display_name"] or class_name or resource}
        if class_name in class_display_names:
            display_name = class_display_names[class_name]
            label["name"] = display_name
            if display_name in class_pages:
                label["page"] = class_pages[display_name]
        class_labels[resource] = label
        mitigations[resource] = float(str(row["mitigation_bonus"]))
    summoners: defaultdict[str, list[Mapping[str, object]]] = defaultdict(list)
    for relation in character_repo.get_character_data_summoners():
        reference = {"key": relation["ability_key"], "name": relation["name"]}
        if relation["page"] is not None:
            reference["page"] = relation["page"]
        summoners[str(relation["character_stable_key"])].append(reference)
    character_records = build_character_generation_records(
        character_repo=character_repo,
        provenance_repo=provenance_repo,
        treasure_repo=treasure_repo,
        catalog=character_catalog,
        class_labels=class_labels,
        constants=character_repo.get_character_data_spawn_constants(),
        mitigations=mitigations,
        build=build,
        lifecycle=lifecycle,
        summoned_by_character=summoners,
        common_world_characters=provenance_repo.get_common_world_character_keys(),
    )
    with tempfile.TemporaryDirectory(prefix="erenshor-wiki-lua-") as temporary:
        staging_root = Path(temporary)
        staged_paths = [
            *write_items_modules(
                item_repo,
                staging_root,
                provenance_repo=provenance_repo,
                class_display_names=class_display_names,
            ),
            *write_items_v2_modules(
                item_repo,
                provenance_repo,
                staging_root,
                build=build,
                native_catalog=character_catalog,
                class_display_names=class_display_names,
                lifecycle=lifecycle,
                max_page_bytes=max_page_bytes * 3 // 4,
                validate=validate,
            ),
            *write_characters_modules(character_records, staging_root, max_page_bytes=max_page_bytes),
            write_links_module(link_entries, staging_root),
            write_spells_module(
                spell_repo,
                staging_root,
                item_repo,
                character_repo,
                class_display_names=class_display_names,
            ),
            write_skills_module(skill_repo, staging_root, item_repo),
            write_stances_module(stance_repo, staging_root),
            write_stance_relations_module(stance_repo, skill_repo, staging_root),
            write_entity_lifecycle_module(lifecycle, staging_root),
            write_build_module(build_repo, staging_root),
            write_treasure_guardians_module(treasure_repo, staging_root),
            write_vendor_stock_module(character_repo, items, provenance_repo, known_keys, staging_root),
            write_world_drops_module(provenance_repo, known_keys, staging_root),
            write_zone_rosters_module(character_repo, known_keys, staging_root, quest_catalog=character_catalog),
            write_class_abilities_module(spell_repo, provenance_repo, known_keys, staging_root),
            write_quests_module(quest_repo, known_keys, staging_root, native_catalog=character_catalog),
            write_progression_module(
                progression_repo,
                known_keys,
                staging_root,
                native_catalog=character_catalog,
                max_page_bytes=max_page_bytes,
            ),
            write_game_board_module(
                character_repo,
                provenance_repo,
                known_keys,
                staging_root,
                reference_catalog=character_catalog,
            ),
        ]
        validation_tools: dict[Path, str] = {}
        for path in staged_paths:
            validation = validate(path)
            output_path = output_root / path.relative_to(staging_root)
            validation_tools[output_path] = validation.tool
        for path in staged_paths:
            size = path.stat().st_size
            # Item data leaves one quarter of the host's page limit unused.
            item_page = path.parent.name in {"ItemsV2", "ItemProvenanceV1"} or path.name == "ItemsV2.lua"
            page_budget = max_page_bytes * 3 // 4 if item_page else max_page_bytes
            if size > page_budget:
                title = "Module:" + path.relative_to(staging_root).with_suffix("").as_posix()
                raise ValueError(f"{title} is {size} bytes. Limit: {page_budget} bytes.")
        written_paths = []
        for path in staged_paths:
            output_path = output_root / path.relative_to(staging_root)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, output_path)
            written_paths.append(output_path)
        manifest_paths = []
        for path in sorted(staging_root.glob("*-provenance.json")):
            output_path = output_root / path.name
            shutil.copyfile(path, output_path)
            manifest_paths.append(output_path)
    _remove_stale_data_modules(output_root, written_paths)

    return LuaDataModuleGenerationResult(
        written_paths=written_paths,
        validation_tools=validation_tools,
        manifest_paths=tuple(manifest_paths),
    )
