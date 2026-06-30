from __future__ import annotations

from pathlib import Path
from typing import cast

from tests.unit.application.wiki_lua.fakes import FakeSpellRepository, make_spell

from erenshor.application.wiki_lua.spells import (
    build_spells_data,
    generate_spells_module,
    write_spells_module,
)
from erenshor.domain.value_objects.wiki_link import CharacterLink, ItemLink


def test_builds_spell_data_with_authoritative_raw_fields() -> None:
    spell = make_spell(
        stable_key="spell:dru - minor lightning",
        display_name="Minor Lightning",
        wiki_page_name="Minor Lightning",
        image_name="Minor Lightning",
        spell_desc="85 Magical damage on target, secondary damage on nearby targets.",
        type="AE",
        line="Direct_Damage",
        required_level=6,
        mana_cost=30,
        sim_usable=1,
        aggro=0,
        spell_charge_time=140.0,
        cooldown=8.0,
        spell_duration_in_ticks=0,
        unstable_duration=0,
        instant_effect=0,
        spell_range=30.0,
        self_only=0,
        max_level_target=0,
        group_effect=0,
        can_hit_players=1,
        apply_to_caster=0,
        inflict_on_self=0,
        target_damage=85,
        target_healing=0,
        caster_healing=0,
        shielding_amt=0,
        lifetap=0,
        damage_type="Magic",
        resist_modifier=0.0,
        add_proc_stable_key="spell:arc - aetherstorm",
        add_proc_chance=12,
        hp=0,
        ac=0,
        mana=0,
        percent_mana_restoration=0,
        movement_speed=0.0,
        str=0,
        dex=0,
        end=0,
        agi=0,
        wis=0,
        int=0,
        cha=0,
        mr=0,
        er=0,
        pr=0,
        vr=0,
        damage_shield=0,
        haste=0.0,
        percent_lifesteal=0.0,
        atk_roll_modifier=0,
        bleed_damage_percent=0,
        root_target=0,
        stun_target=0,
        charm_target=0,
        fear_target=0,
        crowd_control_spell=0,
        break_on_damage=0,
        break_on_any_action=0,
        taunt_spell=0,
        pet_to_summon_stable_key="character:spectral_wolf",
        status_effect_to_apply_stable_key="spell:dru - minor lightning dot",
        reap_and_renew=0,
        resonate_chance=0,
        xp_bonus=0.0,
        automate_attack=1,
        worn_effect=0,
        status_effect_message_on_player="are jolted by lightning.",
        status_effect_message_on_npc="is jolted by lightning.",
    )

    data = build_spells_data([spell], {spell.stable_key: ["Stormcaller", "Druid"]})

    assert data == {
        "spells": {
            "spell:dru - minor lightning": {
                "name": "Minor Lightning",
                "page": "Minor Lightning",
                "image": "Minor Lightning",
                "description": "85 Magical damage on target, secondary damage on nearby targets.",
                "type": "AE",
                "line": "Direct_Damage",
                "classes": ["Druid", "Stormcaller"],
                "requiredLevel": 6,
                "manaCost": 30,
                "simUsable": True,
                "aggro": 0,
                "castTimeSeconds": 2.33,
                "cooldownSeconds": 8.0,
                "durationSeconds": 0,
                "unstableDuration": False,
                "instantEffect": False,
                "range": 30.0,
                "selfOnly": False,
                "maxLevelTarget": 0,
                "groupEffect": False,
                "canHitPlayers": True,
                "applyToCaster": False,
                "inflictOnSelf": False,
                "targetDamage": 85,
                "targetHealing": 0,
                "casterHealing": 0,
                "shieldAmount": 0,
                "lifetap": False,
                "damageType": "Magic",
                "resistModifier": 0.0,
                "addProcStableKey": "spell:arc - aetherstorm",
                "addProcChance": 12,
                "hp": 0,
                "ac": 0,
                "mana": 0,
                "percentManaRestoration": 0,
                "movementSpeed": 0.0,
                "str": 0,
                "dex": 0,
                "end": 0,
                "agi": 0,
                "wis": 0,
                "int": 0,
                "cha": 0,
                "mr": 0,
                "er": 0,
                "pr": 0,
                "vr": 0,
                "damageShield": 0,
                "haste": 0.0,
                "lifesteal": 0.0,
                "atkRollModifier": 0,
                "bleedDamagePercent": 0,
                "root": False,
                "stun": False,
                "charm": False,
                "fear": False,
                "crowdControl": False,
                "breakOnDamage": False,
                "breakOnAnyAction": False,
                "taunt": False,
                "petToSummonStableKey": "character:spectral_wolf",
                "statusEffectStableKey": "spell:dru - minor lightning dot",
                "reapAndRenew": False,
                "resonance": 0,
                "xpBonus": 0.0,
                "automateAttack": True,
                "wornEffect": False,
                "grantInvisibility": False,
                "cannotInterrupt": False,
                "jolt": False,
                "noResonate": False,
                "statusEffectMessageOnPlayer": "are jolted by lightning.",
                "statusEffectMessageOnNpc": "is jolted by lightning.",
            }
        }
    }


def test_builds_spell_relationship_fields_from_repository_links() -> None:
    spell = make_spell(stable_key="spell:minor_lightning")
    teaching_item = ItemLink(page_title="Scroll of Minor Lightning", display_name="Scroll of Minor Lightning")
    effect_item = ItemLink(page_title="Storm Wand", display_name="Storm Wand")
    hidden_effect_item = ItemLink(page_title=None, display_name="Hidden Debug Item")
    caster = CharacterLink(page_title="Storm Caller", display_name="Storm Caller")

    data = build_spells_data(
        [spell],
        {spell.stable_key: []},
        teaching_items_by_spell={spell.stable_key: [teaching_item]},
        items_with_effect_by_spell={spell.stable_key: [hidden_effect_item, effect_item]},
        used_by_by_spell={spell.stable_key: [caster]},
    )

    spells = cast("dict[str, object]", data["spells"])
    record = cast("dict[str, object]", spells[spell.stable_key])
    assert record["source"] == [
        {"kind": "item", "page": "Scroll of Minor Lightning", "text": "Scroll of Minor Lightning"}
    ]
    assert record["itemsWithEffect"] == [{"kind": "item", "page": "Storm Wand", "text": "Storm Wand"}]
    assert record["usedBy"] == [{"kind": "character", "page": "Storm Caller", "text": "Storm Caller"}]


def test_omits_unrenderable_spell_records_and_blank_optional_text() -> None:
    complete = make_spell(
        stable_key="spell:minor_lightning",
        display_name=None,
        wiki_page_name="Minor Lightning",
        image_name="",
        spell_desc="",
        special_descriptor="",
    )
    missing_name = make_spell(
        stable_key="spell:missing",
        display_name=None,
        wiki_page_name=None,
        spell_name=None,
    )

    data = build_spells_data([missing_name, complete], {"spell:minor_lightning": []})

    spells = cast("dict[str, object]", data["spells"])
    assert set(spells) == {"spell:minor_lightning"}
    record = cast("dict[str, object]", spells["spell:minor_lightning"])
    assert record["name"] == "Minor Lightning"
    assert record["page"] == "Minor Lightning"
    assert record["classes"] == []
    assert "image" not in record
    assert "description" not in record
    assert "specialDescriptor" not in record


def test_generates_spells_module_from_repository() -> None:
    module = generate_spells_module(FakeSpellRepository([make_spell()], {"spell:minor_lightning": ["Druid"]}))

    assert module.startswith("return {\n")
    assert '["spell:minor_lightning"]' in module
    assert '"Druid"' in module


def test_writes_spells_module_to_data_module_path(tmp_path: Path) -> None:
    output_path = write_spells_module(FakeSpellRepository([make_spell()], {}), tmp_path)

    assert output_path == tmp_path / "Erenshor" / "Data" / "Spells.lua"
    assert output_path.read_text(encoding="utf-8").startswith("return {\n")


def test_spell_lua_record_includes_mechanics_fields_with_nondefault_values() -> None:
    spell = make_spell(
        armor_pen_percent=25,
        level_scaled_mana_restoration=1.5,
        shapeshift_form="Wolf",
    )
    data = build_spells_data([spell], {})
    record = data["spells"]["spell:minor_lightning"]
    assert record["armorPenPercent"] == 25
    assert record["levelScaledManaRestoration"] == 1.5
    assert record["shapeshiftForm"] == "Wolf"
