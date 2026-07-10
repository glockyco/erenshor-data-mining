from __future__ import annotations

from pathlib import Path

from tests.unit.application.wiki_lua.fakes import (
    FakeCharacterRepository,
    FakeItemRepository,
    FakeLootRepository,
    FakeQuestRepository,
    FakeSkillRepository,
    FakeSpawnRepository,
    FakeSpellRepository,
    FakeSpellUsageRepository,
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
from erenshor.domain.value_objects.source_info import ObtainedFromInfo, UsedInInfo


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
        item_repo=item_repo,
        character_repo=character_repo,
        spawn_repo=FakeSpawnRepository({}),
        loot_repo=FakeLootRepository({}),
        spell_usage_repo=FakeSpellUsageRepository({}),
        spell_repo=FakeSpellRepository([spell]),
        skill_repo=FakeSkillRepository([skill]),
        stance_repo=FakeStanceRepository([stance]),
        quest_repo=FakeQuestRepository([quest]),
        zone_repo=FakeZoneRepository([zone], {}),
        output_root=tmp_path,
        validate=record_validation,
    )

    items_path = tmp_path / "Erenshor" / "Data" / "Items.lua"
    item_shard_path = tmp_path / "Erenshor" / "Data" / "Items" / "Weapons.lua"
    characters_path = tmp_path / "Erenshor" / "Data" / "Characters.lua"
    ability_links_path = tmp_path / "Erenshor" / "Data" / "AbilityLinks.lua"
    spells_path = tmp_path / "Erenshor" / "Data" / "Spells.lua"
    skills_path = tmp_path / "Erenshor" / "Data" / "Skills.lua"
    quests_path = tmp_path / "Erenshor" / "Data" / "Quests.lua"
    zones_path = tmp_path / "Erenshor" / "Data" / "Zones.lua"
    stances_path = tmp_path / "Erenshor" / "Data" / "Stances.lua"
    assert result.written_paths == [
        items_path,
        item_shard_path,
        characters_path,
        ability_links_path,
        spells_path,
        skills_path,
        quests_path,
        zones_path,
        stances_path,
    ]
    assert result.validation_tools == {
        items_path: "stylua",
        item_shard_path: "stylua",
        characters_path: "stylua",
        ability_links_path: "stylua",
        spells_path: "stylua",
        skills_path: "stylua",
        quests_path: "stylua",
        zones_path: "stylua",
        stances_path: "stylua",
    }
    assert validated_paths == [
        items_path,
        item_shard_path,
        characters_path,
        ability_links_path,
        spells_path,
        skills_path,
        quests_path,
        zones_path,
        stances_path,
    ]
    assert '"Weapons"' in items_path.read_text(encoding="utf-8")
    assert "item:sword_of_flames" in item_shard_path.read_text(encoding="utf-8")
    assert "return {" in characters_path.read_text(encoding="utf-8")
    assert "return {" in ability_links_path.read_text(encoding="utf-8")
    assert "return {" in spells_path.read_text(encoding="utf-8")
    assert "return {" in skills_path.read_text(encoding="utf-8")
    assert "return {" in quests_path.read_text(encoding="utf-8")
    assert "return {" in zones_path.read_text(encoding="utf-8")
    assert "return {" in stances_path.read_text(encoding="utf-8")


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
        item_repo=item_repo,
        character_repo=character_repo,
        spawn_repo=FakeSpawnRepository({}),
        loot_repo=FakeLootRepository({}),
        spell_usage_repo=FakeSpellUsageRepository({}),
        spell_repo=FakeSpellRepository([make_spell()]),
        skill_repo=FakeSkillRepository([make_skill()]),
        stance_repo=FakeStanceRepository([make_stance()]),
        quest_repo=quest_repo,
        zone_repo=FakeZoneRepository([make_zone()], {}),
        output_root=tmp_path,
        validate=lambda path: LuaValidationResult(path=path, tool="stylua"),
    )

    item_shard_text = (tmp_path / "Erenshor" / "Data" / "Items" / "Weapons.lua").read_text(encoding="utf-8")
    assert '["obtainedFrom"] = {' in item_shard_text
    assert '["usedIn"] = {' in item_shard_text
    for removed in ("vendorSource", "source", "questSource", "relatedQuest", "componentFor", "containerDrops"):
        assert f'"{removed}"' not in item_shard_text


def _run_generation(tmp_path: Path) -> object:
    item_repo = FakeItemRepository(items=[make_item()], stats={}, classes={})
    return generate_lua_data_modules(
        item_repo=item_repo,
        character_repo=FakeCharacterRepository([make_character()]),
        spawn_repo=FakeSpawnRepository({}),
        loot_repo=FakeLootRepository({}),
        spell_usage_repo=FakeSpellUsageRepository({}),
        spell_repo=FakeSpellRepository([make_spell()]),
        skill_repo=FakeSkillRepository([make_skill()]),
        stance_repo=FakeStanceRepository([make_stance()]),
        quest_repo=FakeQuestRepository([make_quest()]),
        zone_repo=FakeZoneRepository([make_zone()], {}),
        output_root=tmp_path,
        validate=lambda path: LuaValidationResult(path=path, tool="stylua"),
    )


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
    stale_shard.parent.mkdir(parents=True)
    stale_shard.write_text("return {}\n", encoding="utf-8")
    stale_module.write_text("return {}\n", encoding="utf-8")

    result = _run_generation(tmp_path)

    assert not stale_shard.exists()
    assert not stale_module.exists()
    assert (data_dir / "Items.lua") in result.written_paths
    assert (data_dir / "Items.lua").exists()
