"""Tests that character gameplay flags are present in the clean schema."""

from erenshor.application.processor.writer import Writer


def test_character_gameplay_flag_columns_exist(tmp_path):
    """The clean characters table has columns for exported gameplay flags."""
    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()

    cols = {row[1] for row in writer._conn.execute("PRAGMA table_info(characters)").fetchall()}
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

    cols = {row[1] for row in writer._conn.execute("PRAGMA table_info(characters)").fetchall()}
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

    cols = {row[1] for row in writer._conn.execute("PRAGMA table_info(characters)").fetchall()}
    assert "base_armor_pen_percentage" in cols
    assert "base_attack_roll_modifier" in cols
    assert "cannot_be_snared" in cols

    writer._conn.close()
