"""Executable quest routes retain exact copies, variants, and reward behavior."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def clean(main_clean_db: Path) -> Iterator[sqlite3.Connection]:
    with sqlite3.connect(f"{main_clean_db.as_uri()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        yield connection


def _routes(clean: sqlite3.Connection, quest: str, phase: str) -> list[sqlite3.Row]:
    return clean.execute(
        "SELECT * FROM quest_routes WHERE quest_stable_key = ? AND phase = ? ORDER BY source_stable_key",
        (quest, phase),
    ).fetchall()


def test_hermit_request_starts_with_they_only_while_not_done(clean: sqlite3.Connection) -> None:
    routes = _routes(clean, "quest:a hermit's request", "start")
    assert len(routes) == 1, [dict(route) for route in routes]
    route = routes[0]
    assert (route["method"], route["source_kind"], route["source_stable_key"], route["keywords"]) == (
        "dialog",
        "character",
        "character:a hermit",
        "they",
    )
    dialog = clean.execute(
        "SELECT * FROM character_dialogs WHERE character_stable_key = ? AND dialog_index = ?",
        (route["source_stable_key"], route["dialog_index"]),
    ).fetchone()
    assert dialog is not None
    assert dialog["assign_quest_stable_key"] == "quest:a hermit's request"
    assert dialog["keywords"] == route["keywords"]
    conditions = clean.execute(
        "SELECT gate_key, group_index, atom_index, atom_kind, atom_stable_key "
        "FROM quest_route_conditions WHERE route_key = ?",
        (route["route_key"],),
    ).fetchall()
    assert [tuple(row) for row in conditions] == [
        ("dialog_assignment", 0, 0, "quest_not_done", "quest:a hermit's request")
    ]
    assert route["grants_resource_rewards"] == 0


def test_orion_part_two_starts_from_the_executing_predecessor_resource(clean: sqlite3.Connection) -> None:
    routes = _routes(clean, "quest:tempeststone3", "start")
    assert len(routes) == 1, [dict(route) for route in routes]
    route = routes[0]
    assert (route["method"], route["source_kind"], route["source_stable_key"], route["variant_resource_name"]) == (
        "quest_chain",
        "quest",
        "quest:tempeststone2",
        "Orions Tempest Stone 2",
    )
    variant = clean.execute(
        "SELECT quest_stable_key, assign_new_quest_on_complete_stable_key FROM quest_variants WHERE resource_name = ?",
        (route["variant_resource_name"],),
    ).fetchone()
    assert tuple(variant) == ("quest:tempeststone2", "quest:tempeststone3")


def test_orion_part_two_has_both_exact_trade_holders_and_same_item_bundle(clean: sqlite3.Connection) -> None:
    routes = _routes(clean, "quest:tempeststone3", "completion")
    assert len(routes) == 2, [dict(route) for route in routes]
    assert {route["source_stable_key"] for route in routes} == {
        "character:parmalee gemlyn",
        "character:violetta smithfield 1",
    }
    for route in routes:
        assert (
            route["method"],
            route["source_kind"],
            route["variant_resource_name"],
            route["grants_resource_rewards"],
        ) == ("item_turnin", "character", "Orions Tempest Stone 3", 1), dict(route)
        manager = clean.execute(
            """SELECT COUNT(*) FROM character_quest_manager_quests WHERE character_stable_key = ?
            AND quest_stable_key = ? AND quest_variant_resource_name = ?""",
            (route["source_stable_key"], route["quest_stable_key"], route["variant_resource_name"]),
        ).fetchone()[0]
        assert manager == 1, dict(route)
        items = clean.execute(
            """SELECT item_stable_key, quantity, required_slot FROM quest_required_items
            WHERE quest_variant_resource_name = ? ORDER BY required_slot""",
            (route["variant_resource_name"],),
        ).fetchall()
        assert [tuple(item) for item in items] == [
            ("item:ring - 0 - unsocketed ring", 1, 1),
            ("item:gen - elderstone shard", 1, 2),
            ("item:ore - citrine sandsilver", 1, 3),
        ]
    reward = clean.execute(
        "SELECT xp_on_complete, item_on_complete_stable_key FROM quest_variants "
        "WHERE resource_name = 'Orions Tempest Stone 3'"
    ).fetchone()
    assert tuple(reward) == (100, "item:ring - 20 - tempestalia")


def test_nighthollow_candle_keeps_world_well_and_all_eight_furnished_room_copies(clean: sqlite3.Connection) -> None:
    routes = _routes(clean, "quest:ignitingnighthollow", "completion")
    assert len(routes) == 9, [dict(route) for route in routes]
    expected = {
        "character:flamewell:reliquary:268.49:-0.17:327.55": "L1",
        "character:flamewell:reliquary:268.49:-0.17:339.30": "L2",
        "character:flamewell:reliquary:268.49:-0.17:350.80": "L3",
        "character:flamewell:reliquary:268.49:-0.17:361.80": "L4",
        "character:flamewell:reliquary:281.45:-0.17:327.41": "R1",
        "character:flamewell:reliquary:281.45:-0.17:339.16": "R2",
        "character:flamewell:reliquary:281.45:-0.17:350.66": "R3",
        "character:flamewell:reliquary:281.45:-0.17:361.80": "R4",
    }
    world = "character:flamewell:braxonia:86.83:59.42:593.95"
    assert {route["source_stable_key"] for route in routes} == {*expected, world}
    assert len({route["route_key"] for route in routes}) == 9
    completions = clean.execute(
        """SELECT way_key, need_stable_key FROM progression_needs
        WHERE node_stable_key = 'quest:ignitingnighthollow' AND relation = 'turn in to'"""
    ).fetchall()
    assert len(completions) == 9
    assert {row["need_stable_key"] for row in completions} == {*expected, world}
    for route in routes:
        source = route["source_stable_key"]
        assert (
            route["method"],
            route["source_kind"],
            route["variant_resource_name"],
            route["grants_resource_rewards"],
        ) == ("item_turnin", "character", "Lighting the Nighthollow Candle", 1), dict(route)
        placements = clean.execute(
            """SELECT DISTINCT zone_stable_key, furniture_item_stable_key, furniture_slot
            FROM character_spawns WHERE character_stable_key = ?""",
            (source,),
        ).fetchall()
        if source == world:
            assert [tuple(row) for row in placements] == [("zone:braxonia", None, None)]
        else:
            slot = expected[source]
            assert [tuple(row) for row in placements] == [("zone:reliquary", "item:furniture - brax well", slot)]
            needs = clean.execute(
                "SELECT relation, need_stable_key, slot FROM progression_needs WHERE node_stable_key = ?", (source,)
            ).fetchall()
            assert {tuple(row) for row in needs} == {
                ("in zone", "zone:reliquary", None),
                ("quest done", "quest:claimreliquary", None),
                ("room furnished", "item:furniture - brax well", slot),
            }, source


def test_she_sees_you_completes_at_the_gaze_statue_after_the_guardian_awakens(clean: sqlite3.Connection) -> None:
    routes = _routes(clean, "quest:jawsseen", "completion")
    assert len(routes) == 1, [dict(route) for route in routes]
    route = routes[0]
    assert (route["method"], route["source_kind"], route["source_stable_key"], route["source_group_key"]) == (
        "scripted",
        "zone",
        "zone:jaws",
        None,
    )
    assert route["note"] == "Stand in the statue's gaze"
    assert route["variant_resource_name"] is None
    assert route["grants_resource_rewards"] == 0
    conditions = clean.execute(
        "SELECT atom_kind, atom_stable_key FROM quest_route_conditions WHERE route_key = ?", (route["route_key"],)
    ).fetchall()
    assert [tuple(atom) for atom in conditions] == [("quest_done", "quest:jawsentry")]


def test_missing_person_talk_does_not_execute_configured_resource_rewards(clean: sqlite3.Connection) -> None:
    routes = _routes(clean, "quest:missingpersonkrakengard", "completion")
    assert len(routes) == 1, [dict(route) for route in routes]
    route = routes[0]
    assert (route["method"], route["source_kind"], route["source_stable_key"], route["grants_resource_rewards"]) == (
        "talk",
        "character",
        "character:cirreus alxanth:krakengard:280.64:-9.61:91.17",
        0,
    )
    configured = clean.execute(
        """SELECT resource_name, xp_on_complete, assign_new_quest_on_complete_stable_key
        FROM quest_variants WHERE quest_stable_key = 'quest:missingpersonkrakengard'"""
    ).fetchall()
    assert [tuple(row) for row in configured] == [("Missing Person in Krakengard", 25, "quest:hiddencauseintro")]
    assert route["variant_resource_name"] is None


def test_only_trade_completions_execute_resource_reward_bundles(clean: sqlite3.Connection) -> None:
    counts = {
        tuple(row[:2]): row[2]
        for row in clean.execute("SELECT phase, method, COUNT(*) FROM quest_routes GROUP BY phase, method")
    }
    assert counts[("completion", "talk")] > 0
    assert counts[("completion", "item_turnin")] > 0
    wrong = clean.execute(
        """SELECT quest_stable_key, route_key, phase, method, grants_resource_rewards FROM quest_routes
        WHERE grants_resource_rewards != (phase = 'completion' AND method = 'item_turnin')"""
    ).fetchall()
    assert not wrong, [dict(route) for route in wrong]
