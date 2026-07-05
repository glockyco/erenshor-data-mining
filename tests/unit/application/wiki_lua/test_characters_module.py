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
from erenshor.domain.value_objects.wiki_link import AbilityLink, ZoneLink


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
            item_stable_key="item:bear_hide",
            drop_probability=50.0,
            is_guaranteed=True,
            is_visible=False,
        ),
        LootDropInfo(
            item_stable_key="item:bear_meat",
            drop_probability=28.3,
            is_guaranteed=False,
            is_visible=True,
        ),
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
                "faction": {
                    "kind": "faction",
                    "page": "The Followers of Evil",
                    "text": "The Followers of Evil",
                    "stablekey": "faction:the_followers_of_evil",
                },
                "zones": [{"kind": "zone", "page": "Blacksalt Strand", "text": "Blacksalt Strand"}],
                "coordinates": "1.2 x 2.5 x 3.8",
                "respawn": "2 minutes",
                "dropRates": [
                    {"item": "item:bear_hide", "probability": 50.0, "guaranteed": True},
                    {"item": "item:bear_meat", "probability": 28.3, "visible": True},
                ],
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
                "spells": [{"kind": "ability", "page": "Claw Swipe", "text": "Claw Swipe", "image": "Claw Swipe"}],
                "mapSelector": "enemy:A Grizzly Bear",
                "hasDrops": True,
                "hasSpells": True,
            }
        },
    }


def test_character_template_drops_ungenerated_class_field() -> None:
    template = Path("wiki/templates/Character.wiki").read_text(encoding="utf-8")
    cargo_declare = Path("wiki/templates/Character/CargoDeclare.wiki").read_text(encoding="utf-8")

    # The dual-path template branches on stablekey: the generated (new) infobox
    # is emitted first, the verbatim legacy infobox second. The generated path
    # must never surface the ungenerated `class` field, but the legacy fallback
    # keeps it exactly as the live template had it. Scope the label check to the
    # generated branch (everything before the second infobox) so the legacy
    # branch is allowed to retain `Class:`.
    new_branch = template.split('<infobox type="Character">')[1]

    assert "|field|class" not in template
    assert "<label>Class:</label>" not in new_branch
    assert "|Class=String" not in template
    assert "|Class=String" not in cargo_declare


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


def test_character_lua_record_includes_gameplay_flags_with_nondefault_values() -> None:
    character = make_character(
        can_never_see_invis=1,
        dps_dummy=1,
        is_wyrm=1,
        no_run=1,
        never_aggro=1,
        no_dmg_cap=1,
        can_phantom_strike=1,
        no_self_heal=1,
        aggro_regardless_of_los=1,
        ignore_los_for_aggro=1,
        sim_players_ignore_until_ordered=1,
        enrage=90.0,
    )
    data = build_characters_data(
        [character],
        spawn_infos_by_character={},
        loot_by_character={},
        spells_by_character={},
    )
    record = data["characters"]["character:a_grizzly_bear"]
    assert record["canNeverSeeInvis"] == 1
    assert record["dpsDummy"] == 1
    assert record["isWyrm"] == 1
    assert record["noRun"] == 1
    assert record["neverAggro"] == 1
    assert record["noDmgCap"] == 1
    assert record["canPhantomStrike"] == 1
    assert record["noSelfHeal"] == 1
    assert record["aggroRegardlessOfLOS"] == 1
    assert record["ignoreLOSForAggro"] == 1
    assert record["simPlayersIgnoreUntilOrdered"] == 1
    assert record["enrage"] == 90.0


def test_character_lua_record_includes_base_combat_stats_with_nondefault_values() -> None:
    character = make_character(
        base_armor_pen_percentage=20.0,
        base_attack_roll_modifier=3,
        cannot_be_snared=1,
    )
    data = build_characters_data(
        [character],
        spawn_infos_by_character={},
        loot_by_character={},
        spells_by_character={},
    )
    record = data["characters"]["character:a_grizzly_bear"]
    assert record["baseArmorPenPercentage"] == 20.0
    assert record["baseAttackRollModifier"] == 3
    assert record["cannotBeSnared"] == 1
