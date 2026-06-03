from __future__ import annotations

from pathlib import Path

from tests.unit.application.wiki_lua.fakes import (
    FakeSkillRepository,
    FakeSpellRepository,
    FakeStanceRepository,
    make_skill,
    make_spell,
    make_stance,
)

from erenshor.application.wiki_lua.ability_links import (
    build_ability_links_data,
    generate_ability_links_module,
    write_ability_links_module,
)


def test_builds_ability_link_data_from_spells_skills_and_stances() -> None:
    spell = make_spell(
        stable_key="spell:minor_lightning",
        display_name="Minor Lightning",
        wiki_page_name="Minor Lightning",
        image_name="Minor Lightning",
    )
    skill = make_skill(
        stable_key="skill:double_attack",
        display_name="Double Attack",
        wiki_page_name="Double Attack",
        image_name="Double Attack",
    )
    stance = make_stance(
        stable_key="stance:aggressive",
        display_name="Aggressive",
        wiki_page_name="Aggressive Stance",
        image_name="Aggressive",
    )

    data = build_ability_links_data(spells=[spell], skills=[skill], stances=[stance])

    assert data == {
        "abilities": {
            "skill:double_attack": {
                "name": "Double Attack",
                "page": "Double Attack",
                "image": "Double Attack",
                "kind": "skill",
            },
            "spell:minor_lightning": {
                "name": "Minor Lightning",
                "page": "Minor Lightning",
                "image": "Minor Lightning",
                "kind": "spell",
            },
            "stance:aggressive": {
                "name": "Aggressive",
                "page": "Aggressive Stance",
                "image": "Aggressive",
                "kind": "stance",
            },
        },
    }


def test_generates_ability_links_module_from_repositories() -> None:
    module = generate_ability_links_module(
        spell_repo=FakeSpellRepository([make_spell()]),
        skill_repo=FakeSkillRepository([make_skill()]),
        stance_repo=FakeStanceRepository([make_stance()]),
    )

    assert module.startswith("return {\n")
    assert '["spell:minor_lightning"]' in module
    assert '["skill:double_attack"]' in module
    assert '["stance:aggressive"]' in module


def test_writes_ability_links_module_to_data_module_path(tmp_path: Path) -> None:
    output_path = write_ability_links_module(
        spell_repo=FakeSpellRepository([make_spell()]),
        skill_repo=FakeSkillRepository([make_skill()]),
        stance_repo=FakeStanceRepository([make_stance()]),
        output_root=tmp_path,
    )

    assert output_path == tmp_path / "Erenshor" / "Data" / "AbilityLinks.lua"
    assert output_path.read_text(encoding="utf-8").startswith("return {\n")
