"""Gate conditions: when zone lines, placements, and sources are available.

Each rule that can make a subject unavailable becomes one gate on it. A gate
is a list of groups of atoms: it holds when every atom of one group holds, and
a subject is available when every gate on it holds. ``gate_conditions`` stores
one row per atom, and the guide compiler combines the gates of a subject into
its condition.

The rules come from the export (quest listener activations, spawn points,
furnishings, vendor stock) and from ``barriers.toml``, which states what each
keyed door guards. A keyed door opens when its key is on the keyring or in
the inventory (``Door.OpenOrShut``), so each guarded target gets a key atom.
"""

from __future__ import annotations

import math
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Iterable
    from pathlib import Path

    from .writer import Writer

# Subject kinds by the prefix of a barrier target's stable key.
_TARGET_KINDS = {
    "zoneline:": "zone_line",
    "character:": "character",
    "spawn:": "spawn_point",
    "itembag:": "item_bag",
}
_TARGET_TABLES = {
    "zone_line": ("zone_lines", "stable_key"),
    "character": ("characters", "stable_key"),
    "spawn_point": ("character_spawns", "spawn_point_stable_key"),
    "item_bag": ("item_bags", "stable_key"),
}
# Doors of one doorway stand this close together and share a key. The widest
# pair, the Braxonian gate, stands 7.9 m apart.
_DOUBLE_DOOR_DISTANCE = 8.0


@dataclass(frozen=True, slots=True)
class Atom:
    kind: str
    stable_key: str
    slot: str | None = None


@dataclass(frozen=True, slots=True)
class Gate:
    subject_kind: str
    subject_stable_key: str
    gate: str
    groups: tuple[tuple[Atom, ...], ...]
    item_stable_key: str | None = None


@dataclass(frozen=True, slots=True)
class Barrier:
    """One reviewed entry of barriers.toml: a doorway and what it guards."""

    doors: tuple[str, ...]
    guards: tuple[str, ...]
    reason: str


def process_gates(raw: sqlite3.Connection, writer: Writer, barriers_path: Path) -> None:
    """Write ``gate_conditions`` from the exported rules and barriers.toml."""
    conn = writer.conn
    gates = [
        *_activation_gates(raw, conn),
        *_spawn_gates(conn),
        *_furnishing_gates(conn),
        *_vendor_gates(conn),
        *_door_gates(conn, load_barriers(barriers_path)),
    ]
    _validate_atoms(conn, gates)
    rows: list[dict[str, object]] = [
        {
            "subject_kind": gate.subject_kind,
            "subject_stable_key": gate.subject_stable_key,
            "item_stable_key": gate.item_stable_key,
            "gate": gate.gate,
            "group_index": index,
            "atom_kind": atom.kind,
            "atom_stable_key": atom.stable_key,
            "atom_slot": atom.slot,
        }
        for gate in gates
        for index, group in enumerate(gate.groups)
        for atom in group
    ]
    writer.insert_gate_conditions(rows)
    logger.info(f"Gate conditions: {len(gates)} gates, {len(rows)} atoms")


def load_barriers(path: Path) -> list[Barrier]:
    """Read barriers.toml. Raise on a malformed entry."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    barriers: list[Barrier] = []
    for index, entry in enumerate(data.get("barriers", [])):
        doors = entry.get("doors")
        guards = entry.get("guards")
        reason = entry.get("reason")
        if not isinstance(doors, list) or not doors or not all(isinstance(door, str) for door in doors):
            raise ValueError(f"{path.name} entry {index} needs a non-empty list of doors")
        if not isinstance(guards, list) or not all(isinstance(guard, str) for guard in guards):
            raise ValueError(f"{path.name} entry {index} needs a list of guarded targets")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{path.name} entry {index} needs a reason")
        unknown = set(entry) - {"doors", "guards", "reason"}
        if unknown:
            raise ValueError(f"{path.name} entry {index} has unknown fields {sorted(unknown)}")
        barriers.append(Barrier(tuple(doors), tuple(guards), reason))
    return barriers


def _activation_gates(raw: sqlite3.Connection, conn: sqlite3.Connection) -> list[Gate]:
    """Zone lines and characters that a quest listener activates."""
    quest_keys = _quest_keys_by_db_name(conn)
    gates: list[Gate] = []
    for table, key_column, kind in (
        ("ZoneLineQuestUnlocks", "ZoneLineStableKey", "zone_line"),
        ("CharacterQuestUnlocks", "CharacterStableKey", "character"),
    ):
        groups: dict[str, dict[int, set[Atom]]] = defaultdict(lambda: defaultdict(set))
        for subject, group, db_name in raw.execute(f"SELECT {key_column}, UnlockGroup, QuestDBName FROM {table}"):
            quest_key = quest_keys.get(db_name)
            if quest_key is None:
                raise ValueError(f"{table} names unknown quest {db_name!r} for {subject!r}")
            groups[subject][group].add(Atom("quest_done", quest_key))
        gates.extend(
            Gate(kind, subject, "activation", _ordered_groups(by_group.values()))
            for subject, by_group in sorted(groups.items())
        )
    return gates


def _spawn_gates(conn: sqlite3.Connection) -> list[Gate]:
    """Spawn points that start after a quest or stop after one."""
    gates = [
        Gate("spawn_point", spawn, "spawn_start", ((Atom("quest_done", quest),),))
        for spawn, quest in conn.execute(
            """
            SELECT DISTINCT spawn_point_stable_key, spawn_upon_quest_complete_stable_key
            FROM character_spawns
            WHERE spawn_point_stable_key IS NOT NULL AND spawn_upon_quest_complete_stable_key IS NOT NULL
            ORDER BY 1
            """
        )
    ]
    # SpawnPoint stops spawning once any of its stop quests is complete.
    stops: dict[str, set[Atom]] = defaultdict(set)
    for spawn, quest in conn.execute("SELECT spawn_point_stable_key, quest_stable_key FROM spawn_point_stop_quests"):
        stops[spawn].add(Atom("quest_not_done", quest))
    gates.extend(
        Gate("spawn_point", spawn, "spawn_stop", (tuple(sorted(atoms, key=_atom_order)),))
        for spawn, atoms in sorted(stops.items())
    )
    return gates


def _furnishing_gates(conn: sqlite3.Connection) -> list[Gate]:
    """Reliquary room placements that stand only while their room holds the set."""
    return [
        Gate("spawn_point", spawn, "furnishing", ((Atom("room_furnished", item, slot),),))
        for spawn, item, slot in conn.execute(
            """
            SELECT DISTINCT spawn_point_stable_key, furniture_item_stable_key, furniture_slot
            FROM character_spawns
            WHERE spawn_point_stable_key IS NOT NULL AND furniture_item_stable_key IS NOT NULL
            ORDER BY 1
            """
        )
    ]


def _vendor_gates(conn: sqlite3.Connection) -> list[Gate]:
    """Vendor stock that a completed quest adds."""
    quests: dict[tuple[str, str], set[str]] = defaultdict(set)
    for copy, item, quest in conn.execute(
        "SELECT copy_stable_key, item_stable_key, quest_stable_key FROM vendor_offers"
        " WHERE quest_stable_key IS NOT NULL"
    ):
        quests[(copy, item)].add(quest)
    return [
        Gate(
            "vendor_item",
            copy,
            "vendor_unlock",
            tuple((Atom("quest_done", quest),) for quest in sorted(quest_keys)),
            item_stable_key=item,
        )
        for (copy, item), quest_keys in sorted(quests.items())
    ]


def _door_gates(conn: sqlite3.Connection, barriers: list[Barrier]) -> list[Gate]:
    """A key atom on every target that a keyed door guards."""
    doors = {
        key: (scene, (x, y, z), item)
        for key, scene, x, y, z, item in conn.execute(
            "SELECT stable_key, scene, x, y, z, key_item_stable_key FROM doors WHERE key_item_stable_key IS NOT NULL"
        )
    }
    items = {key for (key,) in conn.execute("SELECT stable_key FROM items")}
    listed: dict[str, int] = {}
    gates: list[Gate] = []
    for index, barrier in enumerate(barriers):
        keys = set()
        for door in barrier.doors:
            if door not in doors:
                raise ValueError(f"barriers.toml entry {index} names {door!r}, which is not a keyed door of this build")
            if door in listed:
                raise ValueError(f"barriers.toml lists {door!r} in entries {listed[door]} and {index}")
            listed[door] = index
            keys.add(doors[door][2])
        if len(keys) != 1:
            raise ValueError(f"barriers.toml entry {index} joins doors with different keys: {sorted(keys)}")
        first = doors[barrier.doors[0]]
        for door in barrier.doors[1:]:
            scene, position, _ = doors[door]
            if scene != first[0] or math.dist(position, first[1]) > _DOUBLE_DOOR_DISTANCE:
                raise ValueError(f"barriers.toml entry {index} joins doors of different doorways: {barrier.doors}")
        key = keys.pop()
        # A key that the clean build excludes cannot be obtained, so the door stays shut.
        atom = Atom("key_held", key) if key in items else Atom("never", key)
        for target in barrier.guards:
            kind = _target_kind(target)
            _require_target(conn, kind, target, index)
            gates.append(Gate(kind, target, barrier.doors[0], ((atom,),)))
    unlisted = sorted(set(doors) - set(listed))
    if unlisted:
        details = ", ".join(f"{door} ({doors[door][0]}, {doors[door][2]})" for door in unlisted)
        raise ValueError(f"barriers.toml does not classify these keyed doors: {details}")
    return gates


def _target_kind(target: str) -> str:
    for prefix, kind in _TARGET_KINDS.items():
        if target.startswith(prefix):
            return kind
    raise ValueError(f"barriers.toml target {target!r} is not a zone line, character, spawn point, or item bag")


def _require_target(conn: sqlite3.Connection, kind: str, target: str, index: int) -> None:
    table, column = _TARGET_TABLES[kind]
    if conn.execute(f"SELECT 1 FROM {table} WHERE {column} = ? LIMIT 1", (target,)).fetchone() is None:
        raise ValueError(f"barriers.toml entry {index} guards {target!r}, which this build does not contain")


def _validate_atoms(conn: sqlite3.Connection, gates: list[Gate]) -> None:
    quests = {key for (key,) in conn.execute("SELECT stable_key FROM quests")}
    items = {key for (key,) in conn.execute("SELECT stable_key FROM items")}
    known = {
        "quest_done": quests,
        "quest_not_done": quests,
        "item_held": items,
        "key_held": items,
        "room_furnished": items,
    }
    for gate in gates:
        for group in gate.groups:
            for atom in group:
                if atom.kind in known and atom.stable_key not in known[atom.kind]:
                    raise ValueError(
                        f"{gate.gate} gate on {gate.subject_stable_key!r} names unknown {atom.kind} {atom.stable_key!r}"
                    )


def _quest_keys_by_db_name(conn: sqlite3.Connection) -> dict[str, str]:
    return {db_name: key for key, db_name in conn.execute("SELECT stable_key, db_name FROM quests") if db_name}


def _atom_order(atom: Atom) -> tuple[str, str, str]:
    return (atom.kind, atom.stable_key, atom.slot or "")


def _ordered_groups(groups: Iterable[set[Atom]]) -> tuple[tuple[Atom, ...], ...]:
    ordered = {tuple(sorted(group, key=_atom_order)) for group in groups}
    return tuple(sorted(ordered, key=lambda group: [_atom_order(atom) for atom in group]))
