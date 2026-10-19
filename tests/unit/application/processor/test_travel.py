from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from erenshor.application.processor.travel import _JAILS, _RELEASES, parse_spell_change, process_travel, teleport_key
from erenshor.application.processor.writer import Writer

_FACT = "travel.spell_scene_changes"


def _change(**changes: object) -> str:
    change: dict[str, object] = {
        "to": "Windwashed",
        "landing": "755.27,66,474.4",
        "sun": "true",
        "when": ['spell.SpellName == "Portal to Windwashed"'],
        "unless": [],
    }
    change.update(changes)
    return json.dumps(change)


@pytest.fixture
def writer(tmp_path: Path) -> Writer:
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    conn = writer.conn
    for scene in ("Start", "Windwashed", "Reliquary", "Azynthi", "AzynthiClear", "Detention", "Azure", "Stowaway"):
        conn.execute(
            "INSERT INTO zones (stable_key, scene_name, zone_name, display_name, image_name, zone_type)"
            " VALUES (?, ?, ?, ?, ?, 'Outdoor')",
            (f"zone:{scene.lower()}", scene, scene, scene, scene),
        )
    for spell, name in (
        ("spell:winds", "Portal to Windwashed"),
        ("spell:reliquary", "Portal to Reliquary"),
        ("spell:rift", "Dimensional Rift"),
    ):
        conn.execute(
            "INSERT INTO spells (stable_key, spell_name, display_name, image_name) VALUES (?, ?, ?, ?)",
            (spell, name, name, name),
        )
    conn.execute(
        "INSERT INTO items (stable_key, display_name, image_name, item_effect_on_click_stable_key)"
        " VALUES ('item:rune of winds', 'Rune of Winds', 'rune', 'spell:winds')"
    )
    # The jail facts as the shipped code gives them.
    for (fact, key), (scene, when, unless, _) in {**_JAILS, **_RELEASES}.items():
        value = {"to": scene, "landing": "1,2,3", "sun": "false", "when": list(when), "unless": list(unless)}
        conn.execute("INSERT INTO code_facts VALUES (?, ?, ?, 'text')", (fact, key, json.dumps(value)))
    return writer


def _fact(conn: sqlite3.Connection, *values: str) -> None:
    conn.executemany(
        "INSERT INTO code_facts VALUES (?, ?, ?, 'text')",
        [(_FACT, str(index), value) for index, value in enumerate(values)],
    )


def _routes(conn: sqlite3.Connection) -> dict[str, tuple[object, ...]]:
    return {
        row[0]: tuple(row[1:])
        for row in conn.execute(
            "SELECT route_key, mechanism, source_stable_key, from_zone_stable_key, except_zone_stable_key,"
            " to_zone_stable_key FROM travel_routes"
        )
    }


def test_spell_routes_keep_their_scene_conditions_and_teleports_keep_their_keys(writer: Writer) -> None:
    _fact(
        writer.conn,
        _change(),
        _change(
            to="Reliquary",
            landing="275,1.82,309",
            sun="false",
            when=['spell.SpellName == "Portal to Reliquary"'],
            unless=['SceneManager.GetActiveScene ().name == "Reliquary"'],
        ),
        _change(
            to="Azynthi",
            landing="expr:transform.position",
            sun="false",
            when=[
                'spell.SpellName == "Dimensional Rift"',
                '!(SceneManager.GetActiveScene ().name == "Azynthi")',
                'SceneManager.GetActiveScene ().name == "AzynthiClear"',
            ],
        ),
    )
    writer.conn.execute(
        "INSERT INTO items (stable_key, display_name, image_name, item_effect_on_click_stable_key)"
        " VALUES ('item:box', 'Box', 'box', 'spell:reliquary')"
    )
    process_travel(writer)
    routes = _routes(writer.conn)
    assert routes["travel:spell:reliquary:zone:reliquary"] == (
        "spell",
        "spell:reliquary",
        None,
        "zone:reliquary",
        "zone:reliquary",
    )
    # The rift works only from the cleared garden and lands where the caster stands.
    assert routes["travel:spell:rift:zone:azynthi"] == (
        "spell",
        "spell:rift",
        "zone:azynthiclear",
        None,
        "zone:azynthi",
    )
    teleports = writer.conn.execute("SELECT stable_key, teleport_item_stable_key FROM teleports ORDER BY 1").fetchall()
    assert [tuple(row) for row in teleports] == [
        ("teleport:reliquary:275.00:1.82:309.00", "item:box"),
        ("teleport:windwashed:755.27:66.00:474.40", "item:rune of winds"),
    ]


def test_a_saved_destination_has_no_fixed_zone_and_no_teleport(writer: Writer) -> None:
    _fact(
        writer.conn,
        _change(
            to="expr:GameData.BindZone",
            landing="expr:GameData.BindLoc",
            sun="expr:GameData.SunInBindZone",
            when=['spell.SpellName == "Portal to Windwashed"'],
        ),
    )
    process_travel(writer)
    assert _routes(writer.conn)["travel:spell:winds:saved"][4] is None
    assert writer.conn.execute("SELECT count(*) FROM teleports").fetchone()[0] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"when": ['spell.SpellName == "Portal to Windwashed"', "GameData.usingSun"]},
        {"unless": ["GameData.usingSun"]},
        {"to": "expr:GameData.ReliqDest"},
        {"landing": "expr:GameData.ReliqLanding"},
        {"when": ['!(SceneManager.GetActiveScene ().name == "Azynthi")']},
    ],
)
def test_a_condition_or_argument_that_travel_cannot_read_fails(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=_FACT):
        parse_spell_change("0", _change(**changes))


def test_a_fixed_landing_with_two_casting_items_fails(writer: Writer) -> None:
    _fact(writer.conn, _change())
    writer.conn.execute(
        "INSERT INTO items (stable_key, display_name, image_name, item_effect_on_click_stable_key)"
        " VALUES ('item:copy', 'Copy', 'copy', 'spell:winds')"
    )
    with pytest.raises(ValueError, match="expected one item that casts"):
        process_travel(writer)


def _line(conn: sqlite3.Connection, **changes: object) -> None:
    line: dict[str, object] = {
        "stable_key": "zoneline:start:windwashed",
        "scene": "Start",
        "destination_zone_stable_key": "zone:windwashed",
        "object_is_active": 1,
        "component_is_enabled": 1,
        "collider_is_trigger": 1,
        "has_enabled_trigger": 1,
    } | changes
    conn.execute(
        f"INSERT INTO zone_lines ({','.join(line)}) VALUES ({','.join('?' for _ in line)})", tuple(line.values())
    )


@pytest.mark.parametrize("change", [{"object_is_active": 0}, {"component_is_enabled": 0}, {"has_enabled_trigger": 0}])
def test_a_zone_line_that_cannot_send_the_player_is_no_route(writer: Writer, change: dict[str, object]) -> None:
    _fact(writer.conn, _change())
    _line(writer.conn, **change)
    process_travel(writer)
    assert "zoneline:start:windwashed" not in _routes(writer.conn)


def test_an_inactive_zone_line_that_an_effect_activates_is_a_route(writer: Writer) -> None:
    _fact(writer.conn, _change())
    _line(writer.conn, object_is_active=0)
    writer.conn.execute(
        "INSERT INTO gate_conditions (subject_kind, subject_stable_key, gate, group_index, atom_kind, atom_stable_key)"
        " VALUES ('zone_line', 'zoneline:start:windwashed', 'activation:listener', 0, 'quest_done', 'quest:q')"
    )
    process_travel(writer)
    assert _routes(writer.conn)["zoneline:start:windwashed"][4] == "zone:windwashed"


def test_a_stored_return_exit_is_a_route_without_a_fixed_destination(writer: Writer) -> None:
    _fact(writer.conn, _change())
    # Like the Reliquary Hall's exit, it starts hidden until its controller stores a return.
    _line(writer.conn, object_is_active=0)
    writer.conn.execute(
        "INSERT INTO zone_line_destination_contexts (zone_line_stable_key, kind, destination_state_key,"
        " landing_state_key, source_key) VALUES ('zoneline:start:windwashed', 'stored_return', 'saved', 'saved', 'c')"
    )
    process_travel(writer)
    assert _routes(writer.conn)["zoneline:start:windwashed"][4] is None


def test_teleport_key_rounds_the_game_float_like_the_export() -> None:
    assert teleport_key("Hidden", (9.34, 1.0, -114.33)) == "teleport:hidden:9.34:1.00:-114.33"


def test_jail_routes_lead_into_prison_from_anywhere_and_release_from_it(writer: Writer) -> None:
    _fact(writer.conn, _change())
    process_travel(writer)
    rows = writer.conn.execute(
        "SELECT coalesce(from_zone_stable_key, 'any'), to_zone_stable_key FROM travel_routes"
        " WHERE mechanism = 'jail' ORDER BY 1, 2"
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("any", "zone:detention"),
        ("any", "zone:detention"),
        ("any", "zone:detention"),
        ("zone:detention", "zone:azure"),
        ("zone:detention", "zone:stowaway"),
    ]


def test_a_changed_jail_rule_fails_instead_of_keeping_a_stale_note(writer: Writer) -> None:
    _fact(writer.conn, _change())
    writer.conn.execute(
        "UPDATE code_facts SET value = json_set(value, '$.when[0]', 'warnings > 4 && GameData.Jail')"
        " WHERE fact_id = 'travel.jail_obscenities'"
    )
    with pytest.raises(ValueError, match="the jail rule changed"):
        process_travel(writer)
