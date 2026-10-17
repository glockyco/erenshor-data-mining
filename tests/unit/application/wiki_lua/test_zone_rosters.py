from __future__ import annotations

from pathlib import Path

import pytest

from erenshor.application.wiki_lua.views import DataView, ViewDataError, ViewField, view_module_text
from erenshor.application.wiki_lua.zone_rosters import build_zone_roster_rows, write_zone_rosters_module
from erenshor.domain.value_objects.npc_level import npc_level_bounds


def _spawn(**values: object) -> dict[str, object]:
    return {
        "zone": "zone:lake",
        "character": "character:fish",
        "tier": "enemy",
        "level": 10,
        "levelMod": 0,
        "group": False,
        "scales": False,
        "night": False,
        "rare": False,
        "chance": 25.0,
        **values,
    }


@pytest.mark.parametrize(
    ("level", "group", "expected"),
    [
        (1, False, (1, 2)),
        (34, False, (33, 35)),
        (35, False, (35, 35)),
        (1, True, (1, 1)),
        (34, True, (34, 34)),
        (35, True, (35, 35)),
    ],
)
def test_npc_level_boundaries(level: int, group: bool, expected: tuple[int, int]) -> None:
    assert npc_level_bounds(level, group) == expected


def test_roster_folds_copies_without_losing_alternative_conditions() -> None:
    rows = build_zone_roster_rows(
        [
            _spawn(),
            _spawn(),
            _spawn(levelMod=2, chance=50),
            _spawn(night=True, rare=True, chance=5),
            _spawn(
                script="WaveEvent", chance=None, furniture="item:set", quest="quest:start", stopQuests=["quest:stop"]
            ),
        ]
    )["zone:lake"]
    assert len(rows) == 3
    normal = next(row for row in rows if not row["night"] and "script" not in row)
    assert (normal["levelMin"], normal["levelMax"], normal["chanceMin"], normal["chanceMax"]) == (9, 13, 25, 50)
    scripted = next(row for row in rows if "script" in row)
    assert scripted["furniture"] == "item:set" and scripted["stopQuests"] == ["quest:stop"]
    assert "chanceMin" not in scripted
    assert "x" not in scripted and "position" not in scripted


def test_public_writer_applies_spawn_modifier_before_level_threshold(tmp_path: Path) -> None:
    class Repository:
        def get_zone_roster_spawns(self) -> list[dict[str, object]]:
            return [_spawn(level=34, levelMod=1)]

    path = write_zone_rosters_module(Repository(), {"zone:lake", "character:fish"}, tmp_path, quest_catalog={})
    text = path.read_text()
    assert '["levelMin"] = 35' in text and '["levelMax"] = 35' in text
    assert "chanceMin" in text and "from 0 to 100" in text


def test_native_quest_references_preserve_pageless_identity_and_page_backed_links(tmp_path: Path) -> None:
    class Repository:
        def get_zone_roster_spawns(self) -> list[dict[str, object]]:
            return [_spawn(quest="quest:linked", stopQuests=["quest:soulgemleah"])]

    path = write_zone_rosters_module(
        Repository(),
        {"zone:lake", "character:fish", "quest:linked"},
        tmp_path,
        quest_catalog={
            "quest:linked": {"name": "Linked quest", "page": "Linked quest"},
            "quest:soulgemleah": {"name": "Capture Leah's Soul"},
        },
    )
    text = path.read_text()
    assert '["key"] = "quest:soulgemleah"' in text
    assert '["name"] = "Capture Leah\'s Soul"' in text
    assert '["key"] = "quest:linked"' in text
    assert text.count('["page"] = "Linked quest"') == 1


def test_roster_unknown_native_quest_still_fails(tmp_path: Path) -> None:
    class Repository:
        def get_zone_roster_spawns(self) -> list[dict[str, object]]:
            return [_spawn(stopQuests=["quest:missing"])]

    with pytest.raises(ValueError, match="unknown native quest 'quest:missing'"):
        write_zone_rosters_module(Repository(), {"zone:lake", "character:fish"}, tmp_path, quest_catalog={})
    assert not list(tmp_path.rglob("*.lua"))


@pytest.mark.parametrize(
    "reference",
    [
        {"key": "quest:missing", "name": "A quest"},
        {"key": "quest:pageless", "name": "Another label"},
        {"key": "quest:pageless", "name": "A quest", "page": "Invented page"},
        {"key": "quest:linked", "name": "Linked quest"},
        {"key": "quest:linked", "name": "Linked quest", "page": "Another page"},
    ],
)
def test_native_reference_validation_rejects_unknown_or_mismatched_records(reference: dict[str, object]) -> None:
    view = DataView("ReferenceFixture", "Fixture", "zone", (ViewField("quest", "reference", "Quest"),))
    with pytest.raises(ViewDataError):
        view_module_text(
            view,
            {"zone:lake": [{"quest": reference}]},
            {"zone:lake", "quest:linked"},
            reference_catalog={
                "quest:pageless": {"name": "A quest"},
                "quest:linked": {"name": "Linked quest", "page": "Linked quest"},
            },
        )
