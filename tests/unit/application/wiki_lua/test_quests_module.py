from __future__ import annotations

from pathlib import Path

from tests.unit.application.wiki_lua.fakes import FakeQuestRepository, make_quest

from erenshor.application.wiki_lua.quests import build_quests_data, generate_quests_module, write_quests_module
from erenshor.domain.value_objects.faction import FactionModifier


def test_builds_quest_data_from_clean_quests() -> None:
    quest = make_quest(
        stable_key="quest:magical_sword",
        display_name="A Magical Sword in Port Azure",
        wiki_page_name="A Magical Sword in Port Azure",
        image_name="Magical Sword",
        xp_on_complete=450,
        gold_on_complete=12,
        affected_factions=None,
        affected_faction_amounts=None,
        repeatable=0,
    )

    data = build_quests_data(
        [quest],
        {
            "quest:magical_sword": [
                FactionModifier("faction:port_azure", 5, "Port Azure", "Port Azure"),
                FactionModifier("faction:sivakayans", -2, "Sivakayans", "Sivakayans"),
            ],
        },
    )

    assert data == {
        "quests": {
            "quest:magical_sword": {
                "name": "A Magical Sword in Port Azure",
                "page": "A Magical Sword in Port Azure",
                "image": "Magical Sword",
                "repeatable": "No",
                "experience": 450,
                "gold": 12,
                "factionChanges": "[[Port Azure]] +5<br>[[Sivakayans]] -2",
            }
        },
    }


def test_generates_quests_module_from_repository() -> None:
    module = generate_quests_module(FakeQuestRepository([make_quest()]))

    assert module.startswith("return {\n")
    assert '["quest:magical_sword"]' in module
    assert '["byPage"]' not in module


def test_writes_quests_module_to_data_module_path(tmp_path: Path) -> None:
    output_path = write_quests_module(FakeQuestRepository([make_quest()]), tmp_path)

    assert output_path == tmp_path / "Erenshor" / "Data" / "Quests.lua"
    assert output_path.read_text(encoding="utf-8").startswith("return {\n")
