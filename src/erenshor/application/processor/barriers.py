"""Barriers: objects that block access until their mechanism opens them.

``barriers.toml`` records each barrier with its kind, the objects that form it,
the targets they guard, a player-facing name, a reason, and the check that
confirmed the targets. The opening condition never comes from the record. It
comes from the exported mechanism of each object:

- ``door``: the key opens the door (``Door.OpenOrShut``). A quest listener that
  removes the door is a second way through.
- ``removed``: a quest listener or a classified script disables the object.
- ``moved``: a classified script moves the object away (``ShiveringAngel``).
- ``guardians``: a trigger calls guardians unless a quest is done
  (``PietyTrigger``).

A mechanism needs its controller: a listener's host must be active and a script
must be able to run (``Activity``). Every object that a mechanism opens needs a
record, and every object of one record must open under the same condition.
Each guarded target gets one gate named by the barrier's key.
"""

from __future__ import annotations

import math
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .gates import (
    _TARGET_TABLES,
    Atom,
    Gate,
    _atom_order,
    _code_fact_quest,
    _scripted_reference,
    _spawn_encounter_groups,
    _target_kind,
)
from .hierarchy import _and, _simplify
from .scripted_events import own_conditions

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

    from .hierarchy import Activity, Groups

KINDS = frozenset({"door", "removed", "moved", "guardians"})
CHECKS = frozenset({"navmesh", "render", "unconfirmed"})
# Doors of one doorway stand this close together and share a key. The widest
# pair, the Braxonian gate, stands 7.9 m apart.
_DOUBLE_DOOR_DISTANCE = 8.0
# Subject tables whose objects are placements, not barriers.
_SUBJECT_TABLES = ("Characters", "SpawnPoints", "ZoneLines", "ItemBags", "Doors", "UiItemAccessTargets")


@dataclass(frozen=True, slots=True)
class Barrier:
    """One reviewed record of barriers.toml."""

    kind: str
    name: str
    objects: tuple[str, ...]
    targets: tuple[str, ...]
    reason: str
    check: str

    @property
    def key(self) -> str:
        """The stable key that names the barrier and every gate it causes."""
        return self.objects[0]


@dataclass(frozen=True, slots=True)
class Entry:
    """One reviewed record of barriers.toml: the only zone lines that reach a target."""

    target: str
    via: tuple[str, ...]
    reason: str


def load_barriers(path: Path) -> list[Barrier]:
    """Read the [[barriers]] of barriers.toml. Raise on a malformed record."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    barriers: list[Barrier] = []
    for index, record in enumerate(data.get("barriers", [])):
        kind, name, objects = record.get("kind"), record.get("name"), record.get("objects")
        targets, reason, check = record.get("targets"), record.get("reason"), record.get("check")
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError(f"{path.name} entry {index} has kind {kind!r}, not one of {sorted(KINDS)}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{path.name} entry {index} needs a name")
        if not isinstance(objects, list) or not objects or not all(isinstance(key, str) and key for key in objects):
            raise ValueError(f"{path.name} entry {index} needs a non-empty list of objects")
        if not isinstance(targets, list) or not all(isinstance(target, str) for target in targets):
            raise ValueError(f"{path.name} entry {index} needs a list of guarded targets")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{path.name} entry {index} needs a reason")
        if not isinstance(check, str) or check not in CHECKS:
            raise ValueError(f"{path.name} entry {index} has check {check!r}, not one of {sorted(CHECKS)}")
        unknown = set(record) - {"kind", "name", "objects", "targets", "reason", "check"}
        if unknown:
            raise ValueError(f"{path.name} entry {index} has unknown fields {sorted(unknown)}")
        barriers.append(Barrier(kind, name, tuple(objects), tuple(targets), reason, check))
    return barriers


def load_entries(path: Path) -> list[Entry]:
    """Read the [[entries]] of barriers.toml. Raise on a malformed entry."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    entries: list[Entry] = []
    for index, entry in enumerate(data.get("entries", [])):
        target, via, reason = entry.get("target"), entry.get("via"), entry.get("reason")
        if not isinstance(target, str) or not target:
            raise ValueError(f"{path.name} entries {index} needs a target")
        if not isinstance(via, list) or not via or not all(isinstance(line, str) for line in via):
            raise ValueError(f"{path.name} entries {index} needs a non-empty list of zone lines")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{path.name} entries {index} needs a reason")
        unknown = set(entry) - {"target", "via", "reason"}
        if unknown:
            raise ValueError(f"{path.name} entries {index} has unknown fields {sorted(unknown)}")
        entries.append(Entry(target, tuple(via), reason))
    return entries


def _mechanisms(raw: sqlite3.Connection, conn: sqlite3.Connection, activity: Activity) -> dict[str, dict[str, Groups]]:
    """Each barrier object's mechanisms: kind to opening groups, each with its controller's condition."""
    found: dict[str, dict[str, list[tuple[Atom, ...]]]] = defaultdict(lambda: defaultdict(list))

    def add(identity: str, kind: str, groups: Groups) -> None:
        found[identity][kind].extend(groups)

    # code-fact: guide.gates.door_key
    items = {key for (key,) in conn.execute("SELECT stable_key FROM items")}
    for door, key in conn.execute(
        "SELECT stable_key, key_item_stable_key FROM doors WHERE key_item_stable_key IS NOT NULL"
    ):
        # A key that the clean build excludes cannot be obtained, so the door stays shut.
        add(door, "door", ((Atom("key_held", key) if key in items else Atom("never", key),),))

    subject_objects = {
        key for table in _SUBJECT_TABLES for (key,) in raw.execute(f"SELECT DISTINCT ObjectKey FROM {table}")
    }
    listeners: dict[tuple[str, str, str, int], set[Atom]] = defaultdict(set)
    for kind, target, listener, host, group, atom, key in raw.execute(
        "SELECT TargetKind, TargetStableKey, ListenerKey, ListenerObjectKey, GroupIndex, AtomKind, AtomStableKey"
        " FROM QuestActivationEffects WHERE Effect = 'disable' AND ListenerComponentIsEnabled = 1"
        " AND TargetKind IN ('door', 'object')"
    ):
        # A placement's own object is its availability, not a barrier.
        if kind == "object" and target in subject_objects:
            continue
        listeners[target, listener, host, group].add(Atom(atom, key))
    for (target, _, host, _), atoms in listeners.items():
        add(target, "removed", _and((tuple(sorted(atoms, key=_atom_order)),), activity.host(host)))

    for source, rule in raw.execute(
        "SELECT SourceKey, RuleId FROM ScriptedActivators WHERE RuleId IN ('siv_torch_gaze', 'npc_alive',"
        " 'morph_trigger', 'shivering_angel', 'piety_guardians', 'twin_giants', 'bellwain_reveal')"
        " ORDER BY SourceKey"
    ):
        capability = activity.controller(source)
        if rule == "siv_torch_gaze":
            # code-fact: guide.gates.siv_gaze
            quest = _code_fact_quest(raw, conn, "progression.siv_torch.quest")
            opening = _and(((Atom("quest_done", quest),),), capability)
            for obj in _objects(raw, source, "BreakWall"):
                add(obj, "removed", opening)
        elif rule == "npc_alive":
            # code-fact: guide.gates.npc_alive
            # SpawnIfAlive objects stand while the spawn point's NPC lives.
            spawn = _scripted_reference(raw, source, "SpawnPoint", "spawn_point")
            opening = _and(_spawn_encounter_groups(raw, conn, [spawn]), capability)
            for obj in _objects(raw, source, "SpawnIfAlive"):
                add(obj, "removed", opening)
        elif rule == "twin_giants":
            # code-fact: progression.twins.checkin_binding
            # code-fact: progression.twins.cliffs
            # Both cliffs stand while either twin that checked in lives.
            spawns = sorted(
                {
                    str(key)
                    for (key,) in raw.execute(
                        "SELECT ReferenceKey FROM ScriptedActivatorReferences WHERE SourceKey = ?"
                        " AND Field = '$checkin_spawn_point' AND ReferenceKind = 'spawn_point'",
                        (source,),
                    )
                }
            )
            if not spawns:
                raise ValueError(f"Missing checked-in twin spawn points for {source}")
            opening = _and(_spawn_encounter_groups(raw, conn, spawns), capability)
            for field in ("FrostCliff", "InfernoCliff"):
                for obj in _objects(raw, source, field):
                    add(obj, "removed", opening)
        elif rule == "morph_trigger":
            # Entering the trigger disables these objects after enabling its Enable list.
            for obj in _objects(raw, source, "Disable"):
                if obj not in subject_objects:
                    add(obj, "removed", capability)
        elif rule == "shivering_angel":
            # code-fact: guide.gates.angel
            quest = _code_fact_quest(raw, conn, "progression.shivering_angel.quest")
            opening = _and(((Atom("quest_done", quest),),), capability)
            add(_scripted_reference(raw, source, "$host", "object"), "moved", opening)
        elif rule == "bellwain_reveal":
            # code-fact: progression.bellwain.torches
            # code-fact: progression.bellwain.lift
            # Once every torch shows its colour, AngelScript raises its host statue.
            opening = _and(own_conditions(raw, conn, rule), capability)
            add(_scripted_reference(raw, source, "$host", "object"), "moved", opening)
        elif rule == "piety_guardians":
            quest = _scripted_reference(raw, source, "RequiredQuest", "quest")
            # The trigger calls its guardians only while the quest is not done.
            opening = _and(((Atom("quest_done", quest),),), capability)
            add(_scripted_reference(raw, source, "$host", "object"), "guardians", opening)
        else:
            raise ValueError(f"unhandled barrier rule {rule!r} for {source}")
    return {identity: {kind: tuple(groups) for kind, groups in kinds.items()} for identity, kinds in found.items()}


def _opening(obj: str, mechanisms: dict[str, Groups]) -> Groups:
    """The groups under which an object stops blocking, or the reason it never does."""
    groups = [group for kind_groups in mechanisms.values() for group in kind_groups]
    opening = _simplify(groups)
    if opening:
        return opening
    # Keep the atom that explains it, such as a key that the build excludes.
    reason = next((atom for group in groups for atom in group if atom.kind == "never"), Atom("never", obj))
    return ((reason,),)


def _objects(raw: sqlite3.Connection, source: str, field: str) -> list[str]:
    refs = raw.execute(
        "SELECT ReferenceKind, ReferenceKey FROM ScriptedActivatorReferences WHERE SourceKey = ? AND Field = ?",
        (source, field),
    ).fetchall()
    if not refs or any(kind not in ("object", "null", "empty_collection") for kind, _ in refs):
        raise ValueError(f"Missing or unsupported barrier object reference: {source}.{field}")
    return sorted({str(key) for kind, key in refs if kind == "object"})


def _kind(mechanisms: dict[str, Groups]) -> str:
    if "door" in mechanisms:
        return "door"
    if len(mechanisms) != 1:
        raise ValueError(f"an object with several kinds of mechanism: {sorted(mechanisms)}")
    return next(iter(mechanisms))


def process_barriers(
    raw: sqlite3.Connection, conn: sqlite3.Connection, barriers: list[Barrier], activity: Activity
) -> tuple[list[Gate], list[dict[str, object]]]:
    """Return the gate of each guarded target and one row per barrier."""
    mechanisms = _mechanisms(raw, conn, activity)
    doors = {
        key: (scene, (x, y, z)) for key, scene, x, y, z in conn.execute("SELECT stable_key, scene, x, y, z FROM doors")
    }
    listed: dict[str, int] = {}
    gates: list[Gate] = []
    rows: list[dict[str, object]] = []
    for index, barrier in enumerate(barriers):
        openings: set[Groups] = set()
        for obj in barrier.objects:
            if obj not in mechanisms:
                raise ValueError(f"barriers.toml entry {index} names {obj!r}, which no mechanism of this build opens")
            if obj in listed:
                raise ValueError(f"barriers.toml lists {obj!r} in entries {listed[obj]} and {index}")
            listed[obj] = index
            kind = _kind(mechanisms[obj])
            if kind != barrier.kind:
                raise ValueError(f"barriers.toml entry {index} records {obj!r} as {barrier.kind}, but it is {kind}")
            openings.add(_opening(obj, mechanisms[obj]))
        if len(openings) != 1:
            raise ValueError(f"barriers.toml entry {index} joins objects that open differently: {barrier.objects}")
        if barrier.kind == "door":
            first = doors[barrier.key]
            for door in barrier.objects[1:]:
                scene, position = doors[door]
                if scene != first[0] or math.dist(position, first[1]) > _DOUBLE_DOOR_DISTANCE:
                    raise ValueError(
                        f"barriers.toml entry {index} joins doors of different doorways: {barrier.objects}"
                    )
        opening = openings.pop()
        for target in barrier.targets:
            kind = _target_kind(target)
            table, column = _TARGET_TABLES[kind]
            if conn.execute(f"SELECT 1 FROM {table} WHERE {column} = ? LIMIT 1", (target,)).fetchone() is None:
                raise ValueError(f"barriers.toml entry {index} targets {target!r}, which this build does not contain")
            gates.append(Gate(kind, target, barrier.key, opening))
        rows.append({"barrier_key": barrier.key, "kind": barrier.kind, "name": barrier.name})
    unlisted = sorted(set(mechanisms) - set(listed))
    if unlisted:
        details = ", ".join(f"{obj} ({_kind(mechanisms[obj])})" for obj in unlisted)
        raise ValueError(f"barriers.toml does not record these barriers: {details}")
    return gates, rows


def entry_rows(conn: sqlite3.Connection, entries: list[Entry]) -> list[dict[str, object]]:
    """One row per zone line of an entry, after checking that each line leads into the target's scene."""
    scene_queries = {
        "character": "SELECT scene FROM characters WHERE stable_key = ?",
        "spawn_point": "SELECT scene FROM character_spawns WHERE spawn_point_stable_key = ?",
        "item_bag": "SELECT scene FROM item_bags WHERE stable_key = ?",
    }
    rows: list[dict[str, object]] = []
    for index, entry in enumerate(entries):
        kind = _target_kind(entry.target)
        if kind not in scene_queries:
            raise ValueError(f"barriers.toml entries {index} targets {entry.target!r}, which is not a placed target")
        found = conn.execute(scene_queries[kind], (entry.target,)).fetchone()
        if found is None:
            raise ValueError(f"barriers.toml entries {index} targets {entry.target!r}, which this build lacks")
        for line in entry.via:
            if conn.execute(
                "SELECT 1 FROM zone_line_destination_contexts WHERE zone_line_stable_key=?", (line,)
            ).fetchone():
                raise ValueError(
                    f"barriers.toml entries {index}: {line!r} has a stored return destination, not a fixed entry"
                )
            destination = conn.execute(
                "SELECT z.scene_name FROM zone_lines_with_zoning_capability l"
                " JOIN zones z ON z.stable_key = l.destination_zone_stable_key"
                " WHERE l.stable_key = ?",
                (line,),
            ).fetchone()
            if destination is None:
                raise ValueError(f"barriers.toml entries {index} names {line!r}, which this build lacks")
            if destination[0] != found[0]:
                raise ValueError(
                    f"barriers.toml entries {index}: {line!r} leads to {destination[0]}, not to {found[0]}"
                    f" where {entry.target!r} stands"
                )
            rows.append({"target_kind": kind, "target_stable_key": entry.target, "zone_line_stable_key": line})
    return rows
