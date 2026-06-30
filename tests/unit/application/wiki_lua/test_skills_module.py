from __future__ import annotations

from pathlib import Path
from typing import cast

from tests.unit.application.wiki_lua.fakes import FakeSkillRepository, make_skill

from erenshor.application.wiki_lua.skills import (
    build_skills_data,
    generate_skills_module,
    write_skills_module,
)
from erenshor.domain.value_objects.wiki_link import ItemLink


def test_builds_skill_data_with_raw_authoritative_fields() -> None:
    skill = make_skill(
        stable_key="skill:backstab",
        display_name="Backstab",
        wiki_page_name="Backstab",
        image_name="Backstab",
        skill_name="Backstab",
        skill_desc="Deal major damage to your target.. Must be behind target.",
        type_of_skill="Attack",
        cooldown=540.0,
        duelist_required_level=2,
        paladin_required_level=0,
        arcanist_required_level=0,
        druid_required_level=0,
        stormcaller_required_level=0,
        reaver_required_level=0,
        require_behind=1,
        require_2h=0,
        require_dw=0,
        require_bow=0,
        require_shield=0,
        sim_players_autolearn=1,
        stance_to_use_stable_key=None,
        ae_skill=0,
        interrupt=0,
        spawn_on_use_stable_key="character:shadow_decoy",
        effect_to_apply_stable_key="spell:bleeding_wound",
        affect_player=0,
        affect_target=1,
        skill_range=0.0,
        skill_power=0,
        percent_dmg=0.06,
        damage_type="Physical",
        scale_off_weapon=0,
        proc_weap=0,
        proc_shield=0,
        guarantee_proc=0,
        automate_attack=1,
        cast_on_target_stable_key="spell:minor_lightning",
        skill_anim_name="BackstabAnim",
        skill_icon_name="BackstabIcon",
        player_uses="backstabs",
        npc_uses="backstabs",
    )

    data = build_skills_data([skill], {"Duelist": "Windblade"})

    assert data == {
        "skills": {
            "skill:backstab": {
                "name": "Backstab",
                "page": "Backstab",
                "image": "Backstab",
                "description": "Deal major damage to your target.. Must be behind target.",
                "type": "Attack",
                "cooldownSeconds": 9.0,
                "classLevels": [
                    {"className": "Duelist", "displayName": "Windblade", "level": 2},
                ],
                "requireBehind": True,
                "require2h": False,
                "requireDw": False,
                "requireBow": False,
                "requireShield": False,
                "simPlayersAutolearn": True,
                "aeSkill": False,
                "interrupt": False,
                "spawnOnUseStableKey": "character:shadow_decoy",
                "effectStableKey": "spell:bleeding_wound",
                "affectPlayer": False,
                "affectTarget": True,
                "range": 0.0,
                "skillPower": 0,
                "percentDmg": 0.06,
                "damageType": "Physical",
                "scaleOffWeapon": False,
                "procWeap": False,
                "procShield": False,
                "guaranteeProc": False,
                "skillCanCrit": False,
                "automateAttack": True,
                "castOnTargetStableKey": "spell:minor_lightning",
                "skillAnimName": "BackstabAnim",
                "skillIconName": "BackstabIcon",
                "playerUses": "backstabs",
                "npcUses": "backstabs",
            }
        }
    }


def test_builds_skill_relationship_fields_from_repository_links() -> None:
    skill = make_skill(stable_key="skill:backstab")
    teaching_item = ItemLink(page_title="Backstab Manual", display_name="Backstab Manual")
    effect_item = ItemLink(page_title="Assassin Charm", display_name="Assassin Charm")

    data = build_skills_data(
        [skill],
        {},
        teaching_items_by_skill={skill.stable_key: [teaching_item]},
        items_with_effect_by_skill={skill.stable_key: [effect_item]},
    )

    skills = cast("dict[str, object]", data["skills"])
    record = cast("dict[str, object]", skills[skill.stable_key])
    assert record["source"] == [{"kind": "item", "page": "Backstab Manual", "text": "Backstab Manual"}]
    assert record["itemsWithEffect"] == [{"kind": "item", "page": "Assassin Charm", "text": "Assassin Charm"}]


def test_builds_stance_skill_class_levels_without_hardcoding_display_names() -> None:
    skill = make_skill(
        stable_key="skill:stance - aggressive",
        display_name="Stance: Aggressive",
        wiki_page_name="Stance: Aggressive",
        image_name="Stance: Aggressive",
        reaver_required_level=1,
        stance_to_use_stable_key="stance:aggressive",
    )

    data = build_skills_data([skill], {"Reaver": "Reaver"})
    skills = cast("dict[str, object]", data["skills"])
    record = cast("dict[str, object]", skills["skill:stance - aggressive"])

    assert record["stanceStableKey"] == "stance:aggressive"
    assert record["classLevels"] == [{"className": "Reaver", "displayName": "Reaver", "level": 1}]


def test_omits_unrenderable_skill_records_and_blank_optional_text() -> None:
    complete = make_skill(
        stable_key="skill:backstab",
        display_name=None,
        wiki_page_name="Backstab",
        image_name="",
        skill_name=None,
        skill_desc="",
    )
    missing_name = make_skill(
        stable_key="skill:missing",
        display_name=None,
        wiki_page_name=None,
        skill_name=None,
    )

    data = build_skills_data([missing_name, complete], {})

    skills = cast("dict[str, object]", data["skills"])
    assert set(skills) == {"skill:backstab"}
    record = cast("dict[str, object]", skills["skill:backstab"])
    assert record["name"] == "Backstab"
    assert record["page"] == "Backstab"
    assert "image" not in record
    assert "description" not in record


def test_generates_skills_module_from_repository() -> None:
    module = generate_skills_module(
        FakeSkillRepository([make_skill(duelist_required_level=2)], {"Duelist": "Windblade"})
    )

    assert module.startswith("return {\n")
    assert '["skill:double_attack"]' in module
    assert '"Windblade"' in module


def test_writes_skills_module_to_data_module_path(tmp_path: Path) -> None:
    output_path = write_skills_module(FakeSkillRepository([make_skill()], {}), tmp_path)

    assert output_path == tmp_path / "Erenshor" / "Data" / "Skills.lua"
    assert output_path.read_text(encoding="utf-8").startswith("return {\n")


def test_skill_lua_record_includes_skill_can_crit_with_nondefault_value() -> None:
    skill = make_skill(skill_can_crit=1)
    data = build_skills_data([skill], {})
    record = data["skills"]["skill:double_attack"]
    assert record["skillCanCrit"] is True
