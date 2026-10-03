"""Tests that exported gameplay fields are present in clean schemas."""

import pytest

from erenshor.application.processor.characters import (
    _CharData,
    _CharRow,
    _derive_encounter_tier,
    _SpawnRow,
)
from erenshor.application.processor.writer import Writer


def _table_columns(writer: Writer, table_name: str) -> set[str]:
    return {row[1] for row in writer._conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _char_data(
    *,
    boss_xp: float = 0.0,
    level: int = 10,
    friendly: int = 0,
    faction: str = "Evil",
    override: str | None = None,
    spawns: list[_SpawnRow],
) -> _CharData:
    return _CharData(
        char=_CharRow(
            raw={"BossXpMultiplier": boss_xp, "Level": level, "IsFriendly": friendly, "MyFaction": faction},
            stable_key="character:test",
            display_name="Test",
            wiki_page_name="Test",
            image_name="Test",
            is_wiki_generated=1,
            is_map_visible=1,
            encounter_tier_override=override,
        ),
        spawns=spawns,
    )


def _spawn(*, source_script: str | None, x: float) -> _SpawnRow:
    return _SpawnRow(
        spawn_point_stable_key=f"spawn:{x}",
        zone_stable_key="zone:test",
        scene="Test",
        x=x,
        y=0.0,
        z=0.0,
        is_enabled=1,
        is_directly_placed=0,
        is_trigger_spawn=0,
        rare_npc_chance=None,
        level_mod=None,
        spawn_delay_1=None,
        spawn_delay_2=None,
        spawn_delay_3=None,
        spawn_delay_4=None,
        staggerable=None,
        stagger_mod=None,
        night_spawn=None,
        patrol_points=None,
        loop_patrol=None,
        random_wander_range=None,
        spawn_upon_quest_complete_stable_key=None,
        protector_stable_key=None,
        spawn_chance=None if source_script else 100.0,
        is_common=None,
        is_rare=None,
        is_wiki_generated=None,
        is_map_visible=None,
        source_script=source_script,
    )


def _placements(count: int) -> list[_SpawnRow]:
    return [_spawn(source_script=None, x=float(index)) for index in range(count)]


def test_event_spawned_named_character_is_a_boss() -> None:
    member = _char_data(boss_xp=3.0, spawns=[_spawn(source_script="ShivunaxEvent", x=1.0)])

    assert _derive_encounter_tier([member]) == "boss"


def test_named_character_at_several_placements_is_an_elite() -> None:
    assert _derive_encounter_tier([_char_data(boss_xp=5.0, spawns=_placements(14))]) == "elite"


def test_level_forty_raises_boss_xp_like_the_game() -> None:
    assert _derive_encounter_tier([_char_data(level=42, spawns=_placements(20))]) == "elite"
    assert _derive_encounter_tier([_char_data(level=39, spawns=_placements(20))]) == "enemy"


def test_boss_xp_of_one_is_not_named() -> None:
    assert _derive_encounter_tier([_char_data(boss_xp=1.0, spawns=_placements(3))]) == "enemy"


def test_single_placement_is_a_boss_without_boss_xp() -> None:
    member = _char_data(spawns=[*_placements(1), _spawn(source_script="SprinklesEvent", x=9.0)])

    assert _derive_encounter_tier([member]) == "boss"


def test_event_only_character_without_boss_xp_is_an_enemy() -> None:
    member = _char_data(spawns=[_spawn(source_script="SprinklesEvent", x=1.0)])

    assert _derive_encounter_tier([member]) == "enemy"


def test_group_members_share_placements() -> None:
    first = _char_data(boss_xp=4.0, spawns=_placements(1))
    second = _char_data(boss_xp=4.0, spawns=[_spawn(source_script=None, x=7.0)])

    assert _derive_encounter_tier([first, second]) == "elite"


def test_friendly_character_is_an_npc() -> None:
    assert _derive_encounter_tier([_char_data(boss_xp=5.0, friendly=1, spawns=_placements(1))]) == "npc"


def test_treasure_chest_is_a_chest_although_one_placement_makes_a_boss() -> None:
    assert _derive_encounter_tier([_char_data(faction="TreasureChest", spawns=_placements(1))]) == "chest"


def test_group_that_mixes_chests_and_other_characters_fails() -> None:
    chest = _char_data(faction="TreasureChest", spawns=_placements(1))

    with pytest.raises(ValueError, match="mixes TreasureChest"):
        _derive_encounter_tier([chest, _char_data(spawns=_placements(1))])


def test_zone_gameplay_flag_columns_exist(tmp_path):
    """The clean zones table has columns for exported gameplay metadata."""
    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()

    cols = _table_columns(writer, "zones")
    assert "raid_capable" in cols
    assert "use_zone_as_temp_bind" in cols

    writer._conn.close()


def test_character_gameplay_flag_columns_exist(tmp_path):
    """The clean characters table has columns for exported gameplay flags."""
    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()

    cols = _table_columns(writer, "characters")
    assert "can_never_see_invis" in cols
    assert "dps_dummy" in cols
    assert "is_wyrm" in cols
    assert "no_run" in cols
    assert "never_aggro" in cols
    assert "no_dmg_cap" in cols
    assert "can_phantom_strike" in cols
    assert "no_self_heal" in cols
    assert "aggro_regardless_of_los" in cols
    assert "ignore_los_for_aggro" in cols
    assert "sim_players_ignore_until_ordered" in cols
    assert "enrage" in cols

    writer._conn.close()


def test_npc_role_spell_reference_columns_exist(tmp_path):
    """The clean characters table has columns for NPC role spell references."""
    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()

    cols = _table_columns(writer, "characters")
    assert "spawn_with_status_stable_key" in cols
    assert "group_hot_spell_stable_key" in cols
    assert "emit_vitae_spell_stable_key" in cols
    assert "hot_spell_stable_key" in cols
    assert "ae_taunt_spell_stable_key" in cols

    writer._conn.close()


def test_character_base_combat_stat_columns_exist(tmp_path):
    """The clean characters table has columns for exported Stats gameplay fields."""
    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()

    cols = _table_columns(writer, "characters")
    assert "base_armor_pen_percentage" in cols
    assert "base_attack_roll_modifier" in cols
    assert "cannot_be_snared" in cols

    writer._conn.close()


def test_mapping_override_replaces_the_derived_tier() -> None:
    member = _char_data(friendly=1, override="enemy", spawns=_placements(3))

    assert _derive_encounter_tier([member, member]) == "enemy"


def test_override_must_cover_the_whole_group() -> None:
    with pytest.raises(ValueError, match="disagree"):
        _derive_encounter_tier([_char_data(override="enemy", spawns=_placements(1)), _char_data(spawns=_placements(1))])
