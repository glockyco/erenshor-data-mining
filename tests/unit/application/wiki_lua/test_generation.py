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
    characters_path = tmp_path / "Erenshor" / "Data" / "Characters.lua"
    ability_links_path = tmp_path / "Erenshor" / "Data" / "AbilityLinks.lua"
    quests_path = tmp_path / "Erenshor" / "Data" / "Quests.lua"
    zones_path = tmp_path / "Erenshor" / "Data" / "Zones.lua"
    assert result.written_paths == [items_path, characters_path, ability_links_path, quests_path, zones_path]
    assert result.validation_tools == {
        items_path: "stylua",
        characters_path: "stylua",
        ability_links_path: "stylua",
        quests_path: "stylua",
        zones_path: "stylua",
    }
    assert validated_paths == [items_path, characters_path, ability_links_path, quests_path, zones_path]
    assert "return {" in items_path.read_text(encoding="utf-8")
    assert "return {" in characters_path.read_text(encoding="utf-8")
    assert "return {" in ability_links_path.read_text(encoding="utf-8")
    assert "return {" in quests_path.read_text(encoding="utf-8")
    assert "return {" in zones_path.read_text(encoding="utf-8")
