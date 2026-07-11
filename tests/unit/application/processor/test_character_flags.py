"""Tests that exported gameplay fields are present in clean schemas."""

from erenshor.application.processor.characters import (
    _CharData,
    _CharRow,
    _derive_group_rarity,
    _SpawnRow,
)
from erenshor.application.processor.writer import Writer


def _table_columns(writer: Writer, table_name: str) -> set[str]:
    return {row[1] for row in writer._conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _char_data(*, unique: int = 0, spawns: list[_SpawnRow]) -> _CharData:
    return _CharData(
        char=_CharRow(
            raw={"IsUnique": unique, "IsRare": 0, "IsCommon": 0},
            stable_key="character:test",
            display_name="Test",
            wiki_page_name="Test",
            image_name="Test",
            is_wiki_generated=1,
            is_map_visible=1,
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


def test_dynamic_only_group_uses_explicit_non_unique_flag() -> None:
    member = _char_data(spawns=[_spawn(source_script="SprinklesEvent", x=1.0)])

    assert _derive_group_rarity([member]) == (0, 0)


def test_dynamic_only_group_preserves_explicit_unique_flag() -> None:
    member = _char_data(unique=1, spawns=[_spawn(source_script="FernallaFightEvent", x=1.0)])

    assert _derive_group_rarity([member]) == (1, 0)


def test_mixed_group_counts_only_ordinary_spawns() -> None:
    member = _char_data(
        spawns=[
            _spawn(source_script=None, x=1.0),
            _spawn(source_script="SprinklesEvent", x=2.0),
        ]
    )

    assert _derive_group_rarity([member]) == (1, 0)


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
