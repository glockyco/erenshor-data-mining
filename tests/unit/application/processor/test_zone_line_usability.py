"""Zone line usability: a reviewed exclusion first, then the missing physical input."""

from __future__ import annotations

import itertools
import sqlite3
from typing import TYPE_CHECKING

import pytest

from erenshor.application.processor.entities import process_zone_lines
from erenshor.application.processor.writer import Writer

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def databases(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, Writer]]:
    raw = sqlite3.connect(":memory:")
    raw.execute(
        "CREATE TABLE ZoneLines (StableKey varchar PRIMARY KEY NOT NULL, Scene varchar, X float, Y float, Z float,"
        " IsEnabled integer, ObjectIsActive integer, ComponentIsEnabled integer, ColliderIsTrigger integer,"
        " HasEnabledTrigger integer, DisplayText varchar, DestinationZoneStableKey varchar, LandingPositionX float,"
        " LandingPositionY float, LandingPositionZ float, RemoveParty integer, UseSunInNewZone integer)"
    )
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    try:
        yield raw, writer
    finally:
        raw.close()
        writer.conn.close()


def _line(
    raw: sqlite3.Connection,
    key: str = "zoneline:a",
    *,
    active: int = 1,
    component: int = 1,
    trigger: int = 1,
    enabled_trigger: int = 1,
) -> None:
    raw.execute(
        "INSERT INTO ZoneLines (StableKey, Scene, IsEnabled, ObjectIsActive, ComponentIsEnabled, ColliderIsTrigger,"
        " HasEnabledTrigger) VALUES (?, 'A', ?, ?, ?, ?, ?)",
        (key, int(active and component), active, component, trigger, enabled_trigger),
    )


def _usability(writer: Writer) -> list[tuple[object, ...]]:
    rows = writer.conn.execute("SELECT stable_key, is_usable, unusable_reason FROM zone_lines ORDER BY stable_key")
    return [tuple(row) for row in rows]


@pytest.mark.parametrize(("component", "trigger", "enabled_trigger"), list(itertools.product((0, 1), repeat=3)))
@pytest.mark.parametrize("active", [0, 1])
def test_the_first_missing_input_gives_the_reason_whatever_the_activity(
    databases: tuple[sqlite3.Connection, Writer], component: int, trigger: int, enabled_trigger: int, active: int
) -> None:
    raw, writer = databases
    _line(raw, active=active, component=component, trigger=trigger, enabled_trigger=enabled_trigger)
    process_zone_lines(raw, writer, {})
    inputs = (
        (component, "component_disabled"),
        (trigger, "no_trigger_collider"),
        (enabled_trigger, "trigger_collider_disabled"),
    )
    reason = next((reason for present, reason in inputs if not present), None)
    assert _usability(writer) == [("zoneline:a", int(reason is None), reason)]


@pytest.mark.parametrize("component", [0, 1])
def test_a_reviewed_exclusion_wins_and_keeps_the_raw_capability(
    databases: tuple[sqlite3.Connection, Writer], component: int
) -> None:
    raw, writer = databases
    _line(raw, component=component)
    process_zone_lines(raw, writer, {"zoneline:a": "No walk reaches it."})
    assert _usability(writer) == [("zoneline:a", 0, "No walk reaches it.")]
    assert writer.conn.execute("SELECT count(*) FROM zone_lines_with_zoning_capability").fetchone()[0] == component


@pytest.mark.parametrize("column", ["ComponentIsEnabled", "ColliderIsTrigger", "HasEnabledTrigger"])
@pytest.mark.parametrize("value", [None, 2])
def test_a_missing_physical_input_fails_even_for_an_excluded_line(
    databases: tuple[sqlite3.Connection, Writer], column: str, value: int | None
) -> None:
    raw, writer = databases
    _line(raw)
    raw.execute(f"UPDATE ZoneLines SET {column} = ?", (value,))
    with pytest.raises(ValueError, match="must be exported as 0 or 1"):
        process_zone_lines(raw, writer, {"zoneline:a": "No walk reaches it."})


def test_an_exclusion_of_a_line_that_the_export_lacks_fails(databases: tuple[sqlite3.Connection, Writer]) -> None:
    raw, writer = databases
    _line(raw)
    with pytest.raises(ValueError, match="zoneline:gone"):
        process_zone_lines(raw, writer, {"zoneline:gone": "No walk reaches it."})


@pytest.mark.parametrize(("usable", "reason"), [(None, None), (1, "A reason."), (0, None), (0, " ")])
def test_the_clean_table_rejects_incoherent_usability(
    databases: tuple[sqlite3.Connection, Writer], usable: int | None, reason: str | None
) -> None:
    _, writer = databases
    with pytest.raises(sqlite3.IntegrityError):
        writer.insert_zone_lines([{"stable_key": "zoneline:a", "is_usable": usable, "unusable_reason": reason}])


def test_connections_omit_unusable_lines_and_lines_that_a_gate_shuts_for_good(
    databases: tuple[sqlite3.Connection, Writer],
) -> None:
    raw, writer = databases
    for key in ("zoneline:open", "zoneline:gated", "zoneline:either", "zoneline:never", "zoneline:excluded"):
        _line(raw, key)
    _line(raw, "zoneline:disabled", component=0)
    process_zone_lines(raw, writer, {"zoneline:excluded": "No walk reaches it."})
    writer.conn.executemany(
        "INSERT INTO gate_conditions (subject_kind, subject_stable_key, gate, group_index, atom_kind, atom_stable_key)"
        " VALUES ('zone_line', ?, ?, ?, ?, ?)",
        [
            ("zoneline:gated", "door:a", 0, "key_held", "item:key"),
            ("zoneline:either", "activation:b", 0, "never", "object:b"),
            ("zoneline:either", "activation:b", 1, "quest_done", "quest:q"),
            ("zoneline:never", "activation:c", 0, "never", "object:c"),
        ],
    )
    connections = {row[0] for row in writer.conn.execute("SELECT stable_key FROM zone_line_connections")}
    assert connections == {"zoneline:open", "zoneline:gated", "zoneline:either"}
