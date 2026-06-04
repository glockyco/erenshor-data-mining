from __future__ import annotations

from pathlib import Path

from tests.unit.application.wiki_lua.fakes import FakeStanceRepository, make_stance

from erenshor.application.wiki_lua.stances import (
    build_stances_data,
    generate_stances_module,
    write_stances_module,
)


def test_builds_stance_data_with_raw_modifier_values() -> None:
    stance = make_stance(
        stable_key="stance:aggressive",
        display_name="Aggressive",
        wiki_page_name="Aggressive",
        image_name="Stance: Aggressive",
        stance_desc="Gain a 40% increase to physical damage dealt.",
        switch_message="shifts into an aggressive combat stance",
        max_hp_mod=1.0,
        damage_mod=1.4,
        damage_taken_mod=1.4,
        proc_rate_mod=1.0,
        aggro_gen_mod=1.0,
        spell_damage_mod=1.0,
        self_damage_per_attack=0.0,
        self_damage_per_cast=0.0,
        lifesteal_amount=1.0,
        resonance_amount=1.0,
        stop_regen=1,
    )

    data = build_stances_data([stance])

    assert data == {
        "stances": {
            "stance:aggressive": {
                "name": "Aggressive",
                "page": "Aggressive",
                "image": "Stance: Aggressive",
                "description": "Gain a 40% increase to physical damage dealt.",
                "switchMessage": "shifts into an aggressive combat stance",
                "maxHpMod": 1.0,
                "damageMod": 1.4,
                "damageTakenMod": 1.4,
                "procRateMod": 1.0,
                "aggroGenMod": 1.0,
                "spellDamageMod": 1.0,
                "selfDamagePerAttack": 0.0,
                "selfDamagePerCast": 0.0,
                "lifestealAmount": 1.0,
                "resonanceAmount": 1.0,
                "stopRegen": True,
            }
        },
    }


def test_omits_blank_optional_text_fields() -> None:
    stance = make_stance(
        stable_key="stance:normal",
        display_name="Normal",
        wiki_page_name="Normal",
        image_name="Stance: Normal",
        stance_desc=None,
        switch_message=None,
        stop_regen=0,
    )

    record = build_stances_data([stance])["stances"]["stance:normal"]

    assert "description" not in record
    assert "switchMessage" not in record
    assert record["stopRegen"] is False


def test_generates_stances_module_from_repository() -> None:
    module = generate_stances_module(FakeStanceRepository([make_stance()]))

    assert module.startswith("return {\n")
    assert '["stance:aggressive"]' in module


def test_writes_stances_module_to_data_module_path(tmp_path: Path) -> None:
    output_path = write_stances_module(FakeStanceRepository([make_stance()]), tmp_path)

    assert output_path == tmp_path / "Erenshor" / "Data" / "Stances.lua"
    assert output_path.read_text(encoding="utf-8").startswith("return {\n")
