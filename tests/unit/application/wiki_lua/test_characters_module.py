from __future__ import annotations

from pathlib import Path

from tests.unit.application.wiki_lua.fakes import (
    FakeCharacterRepository,
    FakeLootRepository,
    FakeSpawnRepository,
    FakeSpellUsageRepository,
    make_character,
)

from erenshor.application.wiki_lua.characters import (
    build_characters_data,
    generate_characters_module,
    write_characters_module,
)
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
from erenshor.domain.value_objects.wiki_link import AbilityLink, ItemLink, ZoneLink


def test_builds_character_data_with_spawn_loot_and_spell_summaries() -> None:
    character = make_character()
    spawn_infos = [
        CharacterSpawnInfo(
            zone_link=ZoneLink(page_title="Blacksalt Strand", display_name="Blacksalt Strand"),
            base_respawn=120.0,
            x=1.25,
            y=2.5,
            z=3.75,
            spawn_chance=100.0,
            is_rare=False,
            is_unique=False,
            level_mod=1,
        )
    ]
    loot_drops = [
        LootDropInfo(
            item_link=ItemLink(page_title="Bear Meat", display_name="Bear Meat", image_name="Bear Meat"),
            drop_probability=28.3,
            is_guaranteed=False,
            is_actual=True,
            is_common=True,
            is_uncommon=False,
            is_rare=False,
            is_legendary=False,
            is_unique=False,
            is_visible=False,
            item_unique=False,
        )
    ]
    spells = [AbilityLink(page_title="Claw Swipe", display_name="Claw Swipe", image_name="Claw Swipe")]

    data = build_characters_data(
        characters=[character],
        spawn_infos_by_character={character.stable_key: spawn_infos},
        loot_by_character={character.stable_key: loot_drops},
        spells_by_character={character.stable_key: spells},
    )

    assert data == {
        "characters": {
            "character:a_grizzly_bear": {
                "name": "A Grizzly Bear",
                "page": "A Grizzly Bear",
                "image": "A Grizzly Bear",
                "type": "Enemy",
                "faction": "[[The Followers of Evil]]",
                "zones": "[[Blacksalt Strand]]",
                "coordinates": "1.2 x 2.5 x 3.8",
                "respawn": "2 minutes",
                "dropRates": "{{ItemLink|Bear Meat}} (28.3%)",
                "level": 12,
                "levelModMin": 1,
                "levelModMax": 1,
                "levelVarianceMin": -1,
                "levelVarianceMax": 1,
                "xpMultiplier": 1.0,
                "health": 2340,
                "mana": 0,
                "ac": 180,
                "strength": 23,
                "endurance": 40,
                "dexterity": 5,
                "agility": 15,
                "intelligence": 5,
                "wisdom": 5,
                "charisma": 5,
                "magic": "6-14",
                "poison": "6-14",
                "elemental": "6-14",
                "void": "6-14",
                "spells": "{{AbilityLink|Claw Swipe}}",
                "mapSelector": "enemy:A Grizzly Bear",
                "hasDrops": True,
                "hasSpells": True,
            }
        },
    }


def test_character_type_prefers_npc_then_boss_then_rare() -> None:
    npc = make_character(stable_key="character:npc", wiki_page_name="Helpful NPC", is_friendly=1, is_unique=1)
    boss = make_character(stable_key="character:boss", wiki_page_name="Boss Page", is_friendly=0, is_unique=1)
    rare = make_character(
        stable_key="character:rare",
        wiki_page_name="Rare Page",
        is_friendly=0,
        is_unique=0,
        is_rare=1,
        is_common=0,
    )

    data = build_characters_data(
        characters=[rare, boss, npc],
        spawn_infos_by_character={},
        loot_by_character={},
        spells_by_character={},
    )

    assert data["characters"]["character:npc"]["type"] == "NPC"
    assert data["characters"]["character:boss"]["type"] == "Boss"
    assert data["characters"]["character:rare"]["type"] == "Rare"


def test_generates_characters_module_from_repository_data() -> None:
    character = make_character()
    character_repo = FakeCharacterRepository([character])
    spawn_repo = FakeSpawnRepository({})
    loot_repo = FakeLootRepository({})
    spell_repo = FakeSpellUsageRepository({})

    module = generate_characters_module(character_repo, spawn_repo, loot_repo, spell_repo)

    assert module.startswith("return {\n")
    assert '["character:a_grizzly_bear"]' in module
    assert '["byPage"]' not in module


def test_writes_characters_module_to_data_module_path(tmp_path: Path) -> None:
    character = make_character()
    output_path = write_characters_module(
        FakeCharacterRepository([character]),
        FakeSpawnRepository({}),
        FakeLootRepository({}),
        FakeSpellUsageRepository({}),
        tmp_path,
    )

    assert output_path == tmp_path / "Erenshor" / "Data" / "Characters.lua"
    assert output_path.read_text(encoding="utf-8").startswith("return {\n")
