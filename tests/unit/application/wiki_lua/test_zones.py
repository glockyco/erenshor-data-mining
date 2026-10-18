from __future__ import annotations

from pathlib import Path

import pytest

from erenshor.application.wiki_lua.views import ViewDataError
from erenshor.application.wiki_lua.zones import build_zone_overview_rows, write_zones_module
from erenshor.domain.entities.zone import Zone


def _spawn(**changes: object) -> dict[str, object]:
    return {
        "zone": "zone:lake",
        "character": "character:fish",
        "tier": "enemy",
        "damageable": True,
        "friendly": False,
        "level": 10,
        "levelMod": 0,
        "group": False,
        "scales": False,
        **changes,
    }


def test_population_is_character_weighted_and_median_keeps_roll_uncertainty() -> None:
    spawns = [_spawn()] * 100 + [_spawn(character="character:boss", level=35, group=True)]
    row = build_zone_overview_rows({"zone:lake": "Outdoor"}, spawns, [])["zone:lake"][0]
    assert row == {
        "type": "summary",
        "zoneType": "Outdoor",
        "hostileCount": 2,
        "scalingCount": 0,
        "levelMin": 9,
        "levelMedianMin": 22,
        "levelMedianMax": 23,
        "levelMax": 35,
    }
    assert build_zone_overview_rows({"zone:lake": "Outdoor"}, list(reversed(spawns)), []) == {"zone:lake": [row]}


def test_one_character_contributes_its_envelope_across_spawn_modifiers() -> None:
    row = build_zone_overview_rows({"zone:lake": "Dungeon"}, [_spawn(level=34), _spawn(level=34, levelMod=1)], [])[
        "zone:lake"
    ][0]
    assert row["hostileCount"] == 1
    assert (row["levelMin"], row["levelMedianMin"], row["levelMedianMax"], row["levelMax"]) == (33, 33, 35, 35)
    threshold = build_zone_overview_rows({"zone:lake": "Dungeon"}, [_spawn(level=34, levelMod=1)], [])["zone:lake"][0]
    assert threshold["levelMin"] == threshold["levelMax"] == 35


def test_nonhostiles_and_permanently_undamageable_actors_do_not_create_zero_levels() -> None:
    spawns = [
        _spawn(tier="npc", level=99),
        _spawn(tier="chest", level=99),
        _spawn(damageable=False, level=99),
        _spawn(friendly=True, level=99),
    ]
    row = build_zone_overview_rows({"zone:lake": "Outdoor"}, spawns, [])["zone:lake"][0]
    assert row == {"type": "summary", "zoneType": "Outdoor", "hostileCount": 0, "scalingCount": 0}


def test_scaling_copy_removes_the_entire_groups_fixed_level_contribution() -> None:
    row = build_zone_overview_rows(
        {"zone:lake": "Outdoor"}, [_spawn(), _spawn(scales=True), _spawn(character="character:fixed", level=1)], []
    )["zone:lake"][0]
    assert row["hostileCount"] == 2 and row["scalingCount"] == 1
    assert (row["levelMedianMin"], row["levelMedianMax"]) == (1, 2)


def test_connections_retain_conditional_and_open_alternatives_without_inventing_stored_destination() -> None:
    connections = [
        {"zone": "zone:lake", "line": "line:b", "kind": "fixed", "destination": "zone:other", "conditional": 1},
        {"zone": "zone:lake", "line": "line:a", "kind": "fixed", "destination": "zone:other", "conditional": 0},
        {"zone": "zone:lake", "line": "line:c", "kind": "stored_return", "destination": "zone:stale", "conditional": 1},
    ]
    rows = build_zone_overview_rows({"zone:lake": "Outdoor"}, [], connections)["zone:lake"]
    assert [row["conditional"] for row in rows[1:]] == [False, True, True]
    assert "destination" not in rows[-1]


class _Repository:
    def get_all_zones(self) -> list[Zone]:
        return [
            Zone(
                stable_key="zone:lake",
                scene_name="Lake",
                zone_name="Lake",
                is_dungeon=0,
                zone_type="Outdoor",
                display_name="Lake",
                wiki_page_name="Lake",
                image_name="Lake",
                is_wiki_generated=1,
                is_map_visible=1,
            )
        ]

    def get_zone_overview_spawns(self) -> list[dict[str, object]]:
        return [_spawn()]

    def get_zone_overview_connections(self) -> list[dict[str, object]]:
        return [
            {"zone": "zone:lake", "line": "line:exit", "kind": "fixed", "destination": "zone:other", "conditional": 1}
        ]


def test_unknown_native_destination_fails_before_writing(tmp_path: Path) -> None:
    with pytest.raises(ViewDataError, match="unknown native zone"):
        write_zones_module(_Repository(), {"zone:lake"}, tmp_path, native_catalog={})
    assert not list(tmp_path.rglob("*.lua"))


def test_zone_type_is_plain_checked_data(tmp_path: Path) -> None:
    class InvalidRepository(_Repository):
        def get_all_zones(self) -> list[Zone]:
            zone = super().get_all_zones()[0]
            return [zone.model_copy(update={"zone_type": "[[Invented]]"})]

    with pytest.raises(ViewDataError, match=r"zoneType.*wiki markup"):
        write_zones_module(
            InvalidRepository(),
            {"zone:lake"},
            tmp_path,
            native_catalog={"zone:other": {"name": "Native destination"}},
        )
    assert not list(tmp_path.rglob("*.lua"))
