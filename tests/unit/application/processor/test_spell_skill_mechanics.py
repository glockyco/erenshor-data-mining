"""Tests that spell/skill mechanics fields flow from raw to clean DB."""

from erenshor.application.processor.entities import _rename_cols
from erenshor.application.processor.writer import Writer


def _raw_spell_row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "StableKey": "spell:test",
        "SpellDBIndex": 0,
        "Id": "1",
        "SpellName": "Test Spell",
        "ResourceName": "TEST",
        "display_name": "Test Spell",
        "image_name": "Test Spell",
        "wiki_page_name": "Test Spell",
        "ArmorPenPercent": 25,
        "LevelScaledManaRestoration": 1.5,
        "ShapeshiftForm": "Wolf",
        "SimsNeedHelpToLearn": True,
    }
    base.update(overrides)
    return base


def _raw_skill_row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "StableKey": "skill:test",
        "SkillDBIndex": 0,
        "Id": "1",
        "SkillName": "Test Skill",
        "ResourceName": "TEST",
        "display_name": "Test Skill",
        "image_name": "Test Skill",
        "wiki_page_name": "Test Skill",
        "SkillCanCrit": True,
    }
    base.update(overrides)
    return base


def test_spell_mechanics_fields_flow_to_clean(tmp_path):
    """Raw spell mechanics fields become clean spells columns."""
    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()

    raw_rows = _rename_cols([_raw_spell_row()])
    writer.insert_spells(raw_rows)

    row = writer._conn.execute(
        """
        SELECT armor_pen_percent, level_scaled_mana_restoration, shapeshift_form, sims_need_help_to_learn
        FROM spells
        WHERE stable_key = ?
        """,
        ("spell:test",),
    ).fetchone()
    assert row is not None
    assert row[0] == 25
    assert row[1] == 1.5
    assert row[2] == "Wolf"
    assert row[3] == 1

    writer._conn.close()


def test_skill_can_crit_flows_to_clean(tmp_path):
    """Raw Skills SkillCanCrit becomes clean skills.skill_can_crit column."""
    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()

    raw_rows = _rename_cols([_raw_skill_row()])
    writer.insert_skills(raw_rows)

    row = writer._conn.execute(
        "SELECT skill_can_crit FROM skills WHERE stable_key = ?",
        ("skill:test",),
    ).fetchone()
    assert row is not None
    assert row[0] == 1

    writer._conn.close()
