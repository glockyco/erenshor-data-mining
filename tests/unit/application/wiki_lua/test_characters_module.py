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
from erenshor.domain.value_objects.faction import FactionModifier
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo, CharacterSpawnRow
from erenshor.domain.value_objects.wiki_link import AbilityLink, CharacterAbilityUsage, ZoneLink


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
    spawn_rows = [
        CharacterSpawnRow(
            character_key=character.stable_key,
            zone="zone:blacksalt",
            scene="Blacksalt",
            x=1.25,
            y=2.5,
            z=3.75,
            spawn_chance=100.0,
            night_spawn=False,
            spawn_upon_quest_complete=None,
            level_mod=1,
            rare_npc_chance=0,
            spawn_type="normal",
        )
    ]
    ability_usages = [CharacterAbilityUsage(ability_key="spell:claw_swipe", usage="attack")]

    data = build_characters_data(
        characters=[character],
        spawn_infos_by_character={character.stable_key: spawn_infos},
        loot_by_character={character.stable_key: loot_drops},
        spells_by_character={character.stable_key: spells},
        spawn_rows_by_character={character.stable_key: spawn_rows},
        ability_usages_by_character={character.stable_key: ability_usages},
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
                "spawns": [
                    {
                        "zone": "zone:blacksalt",
                        "scene": "Blacksalt",
                        "x": 1.25,
                        "y": 2.5,
                        "z": 3.75,
                        "spawnChance": 100.0,
                        "nightSpawn": False,
                        "levelMod": 1,
                        "rareNpcChance": 0,
                        "spawnType": "normal",
                        "origin": "generated",
                    }
                ],
                "abilities": [{"ability": "spell:claw_swipe", "usage": "attack"}],
                "mapSelector": "enemy:A Grizzly Bear",
                "hasDrops": True,
                "hasSpells": True,
            }
        },
    }


def test_faction_without_stable_key_keeps_typed_fallback_reference() -> None:
    character = make_character(
        my_world_faction_stable_key=None,
        my_world_faction_display_name="The Followers of Evil",
        my_world_faction_wiki_page_name="The Followers of Evil",
    )

    data = build_characters_data(
        [character],
        spawn_infos_by_character={},
        loot_by_character={},
        spells_by_character={},
        spawn_rows_by_character={},
        ability_usages_by_character={},
    )

    assert data["characters"][character.stable_key]["faction"] == {
        "kind": "faction",
        "page": "The Followers of Evil",
        "text": "The Followers of Evil",
    }


def test_excluded_world_faction_remains_plain_text() -> None:
    character = make_character(
        my_world_faction_stable_key="faction:excluded",
        my_world_faction_display_name="Excluded Faction",
        my_world_faction_wiki_page_name=None,
    )

    data = build_characters_data(
        [character],
        spawn_infos_by_character={},
        loot_by_character={},
        spells_by_character={},
        spawn_rows_by_character={},
        ability_usages_by_character={},
    )

    assert data["characters"][character.stable_key]["faction"] == "Excluded Faction"


def test_faction_modifiers_keep_faction_kind_and_stable_key() -> None:
    character = make_character(
        faction_modifiers=[
            FactionModifier(
                faction_stable_key="faction:azureguard",
                modifier_value=-5,
                faction_display_name="The Azure Guard",
                faction_wiki_page_name="The Azure Guard",
            ),
            FactionModifier(
                faction_stable_key="faction:excluded",
                modifier_value=2,
                faction_display_name="Excluded Faction",
                faction_wiki_page_name=None,
            ),
        ]
    )

    data = build_characters_data(
        [character],
        spawn_infos_by_character={},
        loot_by_character={},
        spells_by_character={},
        spawn_rows_by_character={},
        ability_usages_by_character={},
    )

    assert data["characters"][character.stable_key]["factionChange"] == [
        {
            "link": {"kind": "page", "page": "Excluded Faction", "text": "Excluded Faction"},
            "modifier": 2,
        },
        {
            "link": {
                "kind": "faction",
                "stablekey": "faction:azureguard",
            },
            "modifier": -5,
        },
    ]


def test_dynamic_spawn_omits_chance_but_keeps_coordinate() -> None:
    character = make_character(encounter_tier="boss")
    spawn_infos = [
        CharacterSpawnInfo(
            zone_link=ZoneLink(page_title="Plane of Fernalla", display_name="Plane of Fernalla"),
            base_respawn=None,
            x=1124.2,
            y=24.6,
            z=1151.0,
            spawn_chance=None,
            is_rare=False,
            source_script="SprinklesEvent",
        )
    ]

    data = build_characters_data(
        [character],
        spawn_infos_by_character={character.stable_key: spawn_infos},
        loot_by_character={},
        spells_by_character={},
        spawn_rows_by_character={},
        ability_usages_by_character={},
    )

    record = data["characters"][character.stable_key]
    assert "spawnChance" not in record
    assert record["spawnType"] == "Dynamic event spawn"
    assert record["coordinates"] == "1124.2 x 24.6 x 1151.0"


def test_lua_dynamic_only_multiple_spawns_keep_all_coordinates() -> None:
    character = make_character(encounter_tier="boss")
    spawn_infos = [
        CharacterSpawnInfo(
            zone_link=ZoneLink(page_title="Plane of Fernalla", display_name="Plane of Fernalla"),
            base_respawn=None,
            x=1124.2,
            y=24.6,
            z=1151.0,
            spawn_chance=None,
            is_rare=False,
            source_script="SprinklesEvent",
        ),
        CharacterSpawnInfo(
            zone_link=ZoneLink(page_title="Plane of Fernalla", display_name="Plane of Fernalla"),
            base_respawn=None,
            x=1180.5,
            y=24.6,
            z=1151.0,
            spawn_chance=None,
            is_rare=False,
            source_script="SprinklesEvent",
        ),
    ]

    data = build_characters_data(
        [character],
        spawn_infos_by_character={character.stable_key: spawn_infos},
        loot_by_character={},
        spells_by_character={},
        spawn_rows_by_character={},
        ability_usages_by_character={},
    )

    record = data["characters"][character.stable_key]
    assert record["coordinates"] == "1124.2 x 24.6 x 1151.0<br>1180.5 x 24.6 x 1151.0"


def test_lua_mixed_spawn_prefers_ordinary_coordinate_and_chance() -> None:
    character = make_character(encounter_tier="boss")
    spawn_infos = [
        CharacterSpawnInfo(
            zone_link=ZoneLink(page_title="Plane of Fernalla", display_name="Plane of Fernalla"),
            base_respawn=None,
            x=700.0,
            y=24.6,
            z=1151.0,
            spawn_chance=25.0,
            is_rare=False,
        ),
        CharacterSpawnInfo(
            zone_link=ZoneLink(page_title="Plane of Fernalla", display_name="Plane of Fernalla"),
            base_respawn=None,
            x=1124.2,
            y=24.6,
            z=1151.0,
            spawn_chance=None,
            is_rare=False,
            source_script="SprinklesEvent",
        ),
    ]

    data = build_characters_data(
        [character],
        spawn_infos_by_character={character.stable_key: spawn_infos},
        loot_by_character={},
        spells_by_character={},
        spawn_rows_by_character={},
        ability_usages_by_character={},
    )

    record = data["characters"][character.stable_key]
    assert record["spawnChance"] == "25%"
    assert record["coordinates"] == "700.0 x 24.6 x 1151.0"
    assert "spawnType" not in record


def test_enemy_rare_placement_keeps_its_spawn_chance() -> None:
    character = make_character(encounter_tier="enemy")
    spawn = CharacterSpawnInfo(
        zone_link=ZoneLink(page_title="Blacksalt Strand", display_name="Blacksalt Strand"),
        base_respawn=None,
        x=1.0,
        y=2.0,
        z=3.0,
        spawn_chance=10.0,
        is_rare=True,
    )
    data = build_characters_data(
        [character],
        spawn_infos_by_character={character.stable_key: [spawn]},
        loot_by_character={},
        spells_by_character={},
        spawn_rows_by_character={},
        ability_usages_by_character={},
    )

    record = data["characters"][character.stable_key]
    assert record["type"] == "Enemy"
    assert record["spawnChance"] == "10%"


def test_character_type_uses_stored_encounter_tier() -> None:
    npc = make_character(stable_key="character:npc", wiki_page_name="Helpful NPC", encounter_tier="npc")
    boss = make_character(stable_key="character:boss", wiki_page_name="Boss Page", encounter_tier="boss")
    elite = make_character(stable_key="character:elite", wiki_page_name="Elite Page", encounter_tier="elite")
    enemy = make_character(stable_key="character:enemy", wiki_page_name="Enemy Page", encounter_tier="enemy")

    data = build_characters_data(
        characters=[enemy, elite, boss, npc],
        spawn_infos_by_character={},
        loot_by_character={},
        spells_by_character={},
        spawn_rows_by_character={},
        ability_usages_by_character={},
    )

    assert data["characters"]["character:npc"]["type"] == "NPC"
    assert data["characters"]["character:boss"]["type"] == "Boss"
    assert data["characters"]["character:elite"]["type"] == "Elite"
    assert data["characters"]["character:enemy"]["type"] == "Enemy"


def test_generates_characters_module_from_repository_data() -> None:
    character = make_character(spawn_with_status_stable_key="spell:none - lava coat")
    character_repo = FakeCharacterRepository([character])
    spawn_repo = FakeSpawnRepository({})
    loot_repo = FakeLootRepository({})
    spell_repo = FakeSpellUsageRepository({})

    module = generate_characters_module(character_repo, spawn_repo, loot_repo, spell_repo)

    assert module.startswith("return {\n")
    assert '["character:a_grizzly_bear"]' in module
    assert '["byPage"]' not in module
    assert '["spawnWithStatus"] = "spell:none - lava coat"' in module


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
        spawn_rows_by_character={},
        ability_usages_by_character={},
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
        spawn_rows_by_character={},
        ability_usages_by_character={},
    )
    record = data["characters"]["character:a_grizzly_bear"]
    assert record["baseArmorPenPercentage"] == 20.0
    assert record["baseAttackRollModifier"] == 3
    assert record["cannotBeSnared"] == 1


def test_character_lua_record_carries_spawned_status_stable_key() -> None:
    character = make_character(spawn_with_status_stable_key="spell:none - lava coat")

    data = build_characters_data(
        [character],
        spawn_infos_by_character={},
        loot_by_character={},
        spells_by_character={},
        spawn_rows_by_character={},
        ability_usages_by_character={},
    )

    record = data["characters"]["character:a_grizzly_bear"]
    assert record["spawnWithStatus"] == "spell:none - lava coat"
