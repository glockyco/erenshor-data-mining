from __future__ import annotations

from pathlib import Path

import pytest
from tests.unit.application.wiki_lua.fakes import (
    FakeCharacterRepository,
    FakeClassDisplayService,
    FakeFactionRepository,
    FakeItemRepository,
    FakeQuestRepository,
    FakeSkillRepository,
    FakeSpellRepository,
    FakeStanceRepository,
    FakeZoneRepository,
    make_character,
    make_item,
    make_quest,
    make_skill,
    make_spell,
    make_stance,
    make_zone,
)

from erenshor.application.wiki_lua.generation import generate_lua_data_modules
from erenshor.application.wiki_lua.validation import LuaValidationResult
from erenshor.domain.value_objects.source_info import ObtainedFromInfo, UsedInInfo, WorldDropInfo
from erenshor.domain.value_objects.treasure import ChestWave, GuardianScaling, TreasureGuardian


class FakeBuildRepository:
    def get_build_metadata(self) -> tuple[str, str]:
        return "24405256", "2026-07-27T12:34:56+00:00"


class FakeTreasureRepository:
    def get_treasure_guardians(self) -> list[TreasureGuardian]:
        return [TreasureGuardian("character:ancient horror", "Ancient Horror", "Ancient Horror")]

    def get_guardian_scaling(self) -> list[GuardianScaling]:
        return [GuardianScaling("character:ancient horror", 1, 2, 4, 858, 858, 3, 3, 147, 147, 30, 60, 2, 4)]

    def get_chest_waves(self) -> list[ChestWave]:
        return [ChestWave(0, 0.0, 3, 4, 5.0), ChestWave(1, 1.0, None, None, None)]


def test_generates_and_validates_lua_data_modules(tmp_path: Path) -> None:
    item = make_item()
    character = make_character()
    spell = make_spell()
    skill = make_skill()
    stance = make_stance()
    quest = make_quest()
    zone = make_zone()
    item_repo = FakeItemRepository(items=[item], stats={}, classes={})
    character_repo = FakeCharacterRepository([character])
    validated_paths: list[Path] = []

    def record_validation(path: Path) -> LuaValidationResult:
        validated_paths.append(path)
        return LuaValidationResult(path=path, tool="stylua")

    result = generate_lua_data_modules(
        build_repo=FakeBuildRepository(),
        treasure_repo=FakeTreasureRepository(),
        item_repo=item_repo,
        character_repo=character_repo,
        spell_repo=FakeSpellRepository([spell]),
        skill_repo=FakeSkillRepository([skill]),
        stance_repo=FakeStanceRepository([stance]),
        quest_repo=FakeQuestRepository([quest]),
        zone_repo=FakeZoneRepository([zone], {}),
        faction_repo=FakeFactionRepository(),
        class_display=FakeClassDisplayService(),
        output_root=tmp_path,
        max_page_bytes=4194304,
        validate=record_validation,
    )

    build_path = tmp_path / "Erenshor" / "Data" / "Build.lua"
    items_path = tmp_path / "Erenshor" / "Data" / "Items.lua"
    item_shard_path = tmp_path / "Erenshor" / "Data" / "Items" / "Weapons.lua"
    links_path = tmp_path / "Erenshor" / "Data" / "Links.lua"
    spells_path = tmp_path / "Erenshor" / "Data" / "Spells.lua"
    skills_path = tmp_path / "Erenshor" / "Data" / "Skills.lua"
    stances_path = tmp_path / "Erenshor" / "Data" / "Stances.lua"
    treasure_path = tmp_path / "Erenshor" / "Data" / "TreasureGuardians.lua"
    assert result.written_paths == [
        items_path,
        item_shard_path,
        links_path,
        spells_path,
        skills_path,
        stances_path,
        build_path,
        treasure_path,
    ]
    assert result.validation_tools == {
        build_path: "stylua",
        items_path: "stylua",
        item_shard_path: "stylua",
        links_path: "stylua",
        spells_path: "stylua",
        skills_path: "stylua",
        stances_path: "stylua",
        treasure_path: "stylua",
    }
    staging_root = validated_paths[0].parents[2]
    assert [path.relative_to(staging_root) for path in validated_paths] == [
        path.relative_to(tmp_path) for path in result.written_paths
    ]
    assert build_path.read_text(encoding="utf-8") == (
        'return {\n  ["gameBuildId"] = "24405256",\n  ["publishedAt"] = "2026-07-27T12:34:56+00:00",\n}\n'
    )
    assert '"Weapons"' in items_path.read_text(encoding="utf-8")
    assert "item:sword_of_flames" in item_shard_path.read_text(encoding="utf-8")
    links_text = links_path.read_text(encoding="utf-8")
    assert "return {" in links_text
    for stable_key in (
        "item:sword_of_flames",
        "character:a_grizzly_bear",
        "spell:minor_lightning",
        "skill:double_attack",
        "stance:aggressive",
        "quest:magical_sword",
        "zone:PortAzure",
        "faction:the_followers_of_evil",
        "class:windblade",
    ):
        assert stable_key in links_text
    assert "return {" in spells_path.read_text(encoding="utf-8")
    assert "return {" in skills_path.read_text(encoding="utf-8")
    assert "return {" in stances_path.read_text(encoding="utf-8")


def test_generation_validates_nonnull_blank_item_catalog_pages(tmp_path: Path) -> None:
    item = make_item()
    malformed_catalog_item = make_item(stable_key="item:malformed", wiki_page_name="")
    item_repo = FakeItemRepository(
        items=[item],
        catalog_items=[item, malformed_catalog_item],
        stats={},
        classes={},
    )

    with pytest.raises(ValueError, match="Blank link catalog page"):
        generate_lua_data_modules(
            build_repo=FakeBuildRepository(),
            treasure_repo=FakeTreasureRepository(),
            item_repo=item_repo,
            character_repo=FakeCharacterRepository([make_character()]),
            spell_repo=FakeSpellRepository([make_spell()]),
            skill_repo=FakeSkillRepository([make_skill()]),
            stance_repo=FakeStanceRepository([make_stance()]),
            quest_repo=FakeQuestRepository([make_quest()]),
            zone_repo=FakeZoneRepository([make_zone()], {}),
            faction_repo=FakeFactionRepository(),
            class_display=FakeClassDisplayService(),
            output_root=tmp_path,
            max_page_bytes=4194304,
            validate=lambda path: LuaValidationResult(path=path, tool="stylua"),
        )


def test_generation_wires_item_provenance_repositories(tmp_path: Path) -> None:
    item = make_item()
    item_repo = FakeItemRepository(
        items=[item],
        stats={},
        classes={},
        craft_sources={item.stable_key: [ObtainedFromInfo(source_type="craft", source_key="item:crafting_mold")]},
        crafting_material_sources={
            item.stable_key: [UsedInInfo(use_type="craft_material", target_key="item:copper_armor_mold")]
        },
        world_drops={item.stable_key: [WorldDropInfo(probability=0.05, min_level_exclusive=30)]},
    )
    character_repo = FakeCharacterRepository(
        [make_character()],
        drop_sources={
            item.stable_key: [ObtainedFromInfo(source_type="drop", source_key="character:a_croc", probability=50.0)]
        },
    )
    quest_repo = FakeQuestRepository(
        [make_quest()],
        reward_sources={item.stable_key: [ObtainedFromInfo(source_type="quest", source_key="quest:reward")]},
        requirement_sources={item.stable_key: [UsedInInfo(use_type="quest_requirement", target_key="quest:required")]},
    )

    generate_lua_data_modules(
        build_repo=FakeBuildRepository(),
        treasure_repo=FakeTreasureRepository(),
        item_repo=item_repo,
        character_repo=character_repo,
        spell_repo=FakeSpellRepository([make_spell()]),
        skill_repo=FakeSkillRepository([make_skill()]),
        stance_repo=FakeStanceRepository([make_stance()]),
        quest_repo=quest_repo,
        zone_repo=FakeZoneRepository([make_zone()], {}),
        faction_repo=FakeFactionRepository(),
        class_display=FakeClassDisplayService(),
        max_page_bytes=4194304,
        output_root=tmp_path,
        validate=lambda path: LuaValidationResult(path=path, tool="stylua"),
    )

    item_shard_text = (tmp_path / "Erenshor" / "Data" / "Items" / "Weapons.lua").read_text(encoding="utf-8")
    assert '["obtainedFrom"] = {' in item_shard_text
    assert '["usedIn"] = {' in item_shard_text
    assert '["type"] = "world_drop"' in item_shard_text
    assert '["condition"] = "enemy level above 30"' in item_shard_text
    for removed in ("vendorSource", "source", "questSource", "relatedQuest", "componentFor", "containerDrops"):
        assert f'"{removed}"' not in item_shard_text


def _run_generation(tmp_path: Path, *, max_page_bytes: int = 4194304, item_key: str = "item:sword_of_flames") -> object:
    item_repo = FakeItemRepository(items=[make_item(stable_key=item_key)], stats={}, classes={})
    return generate_lua_data_modules(
        build_repo=FakeBuildRepository(),
        treasure_repo=FakeTreasureRepository(),
        item_repo=item_repo,
        character_repo=FakeCharacterRepository([make_character()]),
        spell_repo=FakeSpellRepository([make_spell()]),
        skill_repo=FakeSkillRepository([make_skill()]),
        stance_repo=FakeStanceRepository([make_stance()]),
        quest_repo=FakeQuestRepository([make_quest()]),
        zone_repo=FakeZoneRepository([make_zone()], {}),
        faction_repo=FakeFactionRepository(),
        class_display=FakeClassDisplayService(),
        output_root=tmp_path,
        max_page_bytes=max_page_bytes,
        validate=lambda path: LuaValidationResult(path=path, tool="stylua"),
    )


def test_generated_modules_are_byte_for_byte_deterministic(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first_result = _run_generation(first_root)
    second_result = _run_generation(second_root)

    first_modules = {path.relative_to(first_root): path.read_bytes() for path in first_result.written_paths}
    second_modules = {path.relative_to(second_root): path.read_bytes() for path in second_result.written_paths}
    assert first_modules == second_modules


def test_generation_rejects_oversize_module_without_changing_output(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    item_key = "item:épée"
    _run_generation(reference_root, item_key=item_key)
    module = reference_root / "Erenshor" / "Data" / "Items.lua"
    size = module.stat().st_size
    character_limit = len(module.read_text(encoding="utf-8"))
    assert size > character_limit
    output_root = tmp_path / "output"
    data_dir = output_root / "Erenshor" / "Data"
    data_dir.mkdir(parents=True)
    existing_module = data_dir / "Items.lua"
    existing_module.write_text("return { old = true }\n", encoding="utf-8")

    with pytest.raises(ValueError, match=rf"Module:Erenshor/Data/Items is {size} bytes.*{character_limit} bytes"):
        _run_generation(output_root, max_page_bytes=character_limit, item_key=item_key)

    assert existing_module.read_text(encoding="utf-8") == "return { old = true }\n"
    assert list(data_dir.rglob("*.lua")) == [existing_module]


def test_generation_requires_faction_and_class_dependencies(tmp_path: Path) -> None:
    with pytest.raises(TypeError) as error:
        generate_lua_data_modules(
            build_repo=FakeBuildRepository(),
            treasure_repo=FakeTreasureRepository(),
            item_repo=FakeItemRepository(items=[make_item()], stats={}, classes={}),
            character_repo=FakeCharacterRepository([make_character()]),
            spell_repo=FakeSpellRepository([make_spell()]),
            skill_repo=FakeSkillRepository([make_skill()]),
            stance_repo=FakeStanceRepository([make_stance()]),
            quest_repo=FakeQuestRepository([make_quest()]),
            zone_repo=FakeZoneRepository([make_zone()], {}),
            output_root=tmp_path,
            max_page_bytes=4194304,
            validate=lambda path: LuaValidationResult(path=path, tool="stylua"),
        )

    assert "faction_repo" in str(error.value)
    assert "class_display" in str(error.value)


def test_top_level_written_paths_match_declared_plan(tmp_path: Path) -> None:
    """The declared dry-run plan stays in sync with what generation actually writes."""
    from erenshor.application.wiki_lua.generation import planned_top_level_module_paths

    result = _run_generation(tmp_path)

    data_dir = tmp_path / "Erenshor" / "Data"
    written_top_level = [path for path in result.written_paths if path.parent == data_dir]
    assert written_top_level == planned_top_level_module_paths(tmp_path)


def test_generation_removes_stale_data_modules(tmp_path: Path) -> None:
    """Files left by a previous generation that are no longer produced are removed."""
    data_dir = tmp_path / "Erenshor" / "Data"
    stale_shard = data_dir / "Items" / "001.lua"
    stale_module = data_dir / "Obsolete.lua"
    stale_legacy_module = data_dir / "AbilityLinks.lua"
    stale_shard.parent.mkdir(parents=True)
    stale_shard.write_text("return {}\n", encoding="utf-8")
    stale_module.write_text("return {}\n", encoding="utf-8")
    stale_legacy_module.write_text("return {}\n", encoding="utf-8")

    result = _run_generation(tmp_path)

    assert not stale_shard.exists()
    assert not stale_module.exists()
    assert not stale_legacy_module.exists()
    assert (data_dir / "Items.lua") in result.written_paths
    assert (data_dir / "Items.lua").exists()
