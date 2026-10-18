"""Gate conditions: when zone lines, placements, and sources are available.

Each rule that can make a subject unavailable becomes one gate on it. A gate
is a list of groups of atoms: it holds when every atom of one group holds, and
a subject is available when every gate on it holds. ``gate_conditions`` stores
one row per atom, and the guide compiler combines the gates of a subject into
its condition.

The rules come from the export (quest listener activations, scripted encounters,
spawn points, furnishings, vendor stock) and from ``barriers.toml``, which states what each
keyed door guards. A keyed door opens when its key is on the keyring or in
the inventory (``Door.OpenOrShut``), so each guarded target gets a key atom.

``barriers.toml`` also lists entries: targets that only some of the zone lines
into their scene reach, such as a ledge that one tomb entrance lands on.
``target_entries`` records those zone lines, so navigation enters there.
"""

from __future__ import annotations

import math
import tomllib
from collections import Counter, defaultdict
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

# ShiverEvent checks quest IDs, while all affected placements come from its
# exported references. Keepers are conversations, not encounters.
SHIVER_KEEPER_QUESTS = tuple(f"quest:shiver-{name}" for name in ("watchman", "gatekeeper", "harbinger", "curator"))
SHIVER_MEET_ALL = "quest:shiver-meetall"

# code-fact: guide.gates.planning_raid_portals
_PLANAR_PORTALS = (
    ("FernPort", "PlanarFern", "134379"),
    ("BraxPort", "PlanarBrax", "12094245"),
    ("VithPort", "PlanarVith", "96186750"),
    ("SolPort", "PlanarSol", "25900083"),
)
_PLANAR_SLOTS = frozenset(slot for _, slot, _ in _PLANAR_PORTALS)
# code-fact: guide.gates.planning_portal_items
_RUNE_PORTALS = (
    ("Braxonian", "2096280"),
    ("Ripper", "2810120"),
    ("Silkengrass", "71979710"),
    ("Soluna", "5388624"),
    ("Hidden", "36740470"),
    ("Windwashed", "5016816"),
)
# code-fact: guide.gates.planning_portal_place
_RUNE_SLOTS = tuple(f"Rune{index}" for index in range(1, 7))
_PLANNING_SLOTS = _PLANAR_SLOTS | frozenset(_RUNE_SLOTS)


@dataclass(frozen=True, slots=True)
class PlanningPortalSelection:
    line: str
    slot: str
    slot_kind: str
    item_stable_key: str
    destination_zone_stable_key: str


@dataclass(frozen=True, slots=True)
class Atom:
    kind: str
    stable_key: str
    slot: str | None = None
    quantity: int | None = None


@dataclass(frozen=True, slots=True)
class Gate:
    subject_kind: str
    subject_stable_key: str
    gate: str
    groups: tuple[tuple[Atom, ...], ...]
    item_stable_key: str | None = None
    controller_source_key: str | None = None


@dataclass(frozen=True, slots=True)
class Barrier:
    """One reviewed entry of barriers.toml: a doorway and what it guards."""

    doors: tuple[str, ...]
    guards: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class Entry:
    """One reviewed entry of barriers.toml: the only zone lines that reach a target."""

    target: str
    via: tuple[str, ...]
    reason: str


def process_gates(raw: sqlite3.Connection, writer: Writer, barriers_path: Path) -> None:
    """Write ``gate_conditions`` and ``target_entries`` from the export and barriers.toml."""
    conn = writer.conn
    planning = {
        source: _select_planning_portals(raw, conn, source)
        for (source,) in raw.execute(
            "SELECT SourceKey FROM ScriptedActivators"
            " WHERE RuleId = 'planning_portals' AND ComponentIsEnabled = 1 ORDER BY SourceKey"
        )
    }
    from .hierarchy import apply_hierarchy_activity

    gates = apply_hierarchy_activity(
        raw,
        conn,
        [
            *_shiver_event_gates(raw, conn),
            *_scripted_gates(raw, conn, planning),
            *_spawn_gates(conn),
            *_furnishing_gates(conn),
            *_vendor_gates(conn),
            *_door_gates(conn, load_barriers(barriers_path)),
        ],
    )
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
            "atom_quantity": atom.quantity,
        }
        for gate in gates
        for index, group in enumerate(gate.groups)
        for atom in group
    ]
    writer.insert_gate_conditions(rows)
    writer.insert_planning_portal_slots(
        [
            {"zone_line_stable_key": selection.line, "slot": selection.slot, "slot_kind": selection.slot_kind}
            for selections in planning.values()
            for selection in selections
        ]
    )
    logger.info(f"Gate conditions: {len(gates)} gates, {len(rows)} atoms")
    _shiver_event_quest_sources(raw, writer)
    entries = _entry_rows(conn, load_entries(barriers_path))
    writer.insert_target_entries(entries)
    logger.info(f"Target entries: {len(entries)} zone lines")


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


def load_entries(path: Path) -> list[Entry]:
    """Read the [[entries]] of barriers.toml. Raise on a malformed entry."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    entries: list[Entry] = []
    for index, entry in enumerate(data.get("entries", [])):
        target = entry.get("target")
        via = entry.get("via")
        reason = entry.get("reason")
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


def _entry_rows(conn: sqlite3.Connection, entries: list[Entry]) -> list[dict[str, object]]:
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


def _scripted_reference(raw: sqlite3.Connection, source: str, field: str, kind: str) -> str:
    refs = raw.execute(
        "SELECT ReferenceKind, ReferenceKey FROM ScriptedActivatorReferences WHERE SourceKey = ? AND Field = ?",
        (source, field),
    ).fetchall()
    if len(refs) != 1 or refs[0][0] != kind or not refs[0][1]:
        raise ValueError(f"Missing or ambiguous scripted {kind} reference: {source}.{field}")
    return str(refs[0][1])


def _scripted_targets(
    raw: sqlite3.Connection, conn: sqlite3.Connection, source: str, field: str, mode: str, *, objects: bool = False
) -> list[tuple[str, str]]:
    targets = []
    for kind, key in raw.execute(
        "SELECT DISTINCT t.Kind, t.Key FROM ScriptedActivatorReferences r"
        " JOIN ScriptedActivatorTargets t ON t.ReferenceId = r.ReferenceId"
        " WHERE r.SourceKey = ? AND r.Field = ? AND t.ResolutionMode = ? ORDER BY t.Kind, t.Key",
        (source, field, mode),
    ):
        if kind == "object" and objects:
            targets.append((kind, key))
            continue
        if kind not in _TARGET_TABLES:
            # An object reference proves identity, not what lies behind it.
            continue
        table, column = _TARGET_TABLES[kind]
        if conn.execute(f"SELECT 1 FROM {table} WHERE {column} = ?", (key,)).fetchone() is not None:
            targets.append((kind, key))
    return targets


def _scripted_gates(
    raw: sqlite3.Connection,
    conn: sqlite3.Connection,
    planning: dict[str, tuple[PlanningPortalSelection, ...]] | None = None,
) -> list[Gate]:
    """Use exact controller references, never an actor's name or prefab copies."""
    restored = {
        "restored_fernalla": ("RestoredFernalla", "FernSpawnPoint"),
        "restored_soluna": ("RestoredSoluna", "SolunaSpawn"),
        "restored_brax": ("GodBraxRestored", "BraxSpawn"),
    }
    rules = (
        *restored,
        "restored_vitheo",
        "memory_sphere",
        "shivering_angel",
        "npc_alive",
        "npc_shout_essentials",
        "shivering_phantom_wards",
        "reliquary_wards",
        "planning_portals",
        "astra_deaths",
        "stowaway_deaths",
        "fernalla_portal_wards",
        "bellwain_reveal",
        "morph_trigger",
        "piety_guardians",
    )
    sources = raw.execute(
        "SELECT SourceKey, RuleId FROM ScriptedActivators WHERE RuleId IN ("
        + ",".join("?" for _ in rules)
        + ") ORDER BY SourceKey",
        rules,
    ).fetchall()
    gates: list[Gate] = []
    ward_sources: set[str] = set()
    for source, rule in sources:
        enabled, host, scene, object_name = raw.execute(
            "SELECT ComponentIsEnabled, HostCharacterStableKey, SourceScene, SourceObjectName"
            " FROM ScriptedActivators WHERE SourceKey = ?",
            (source,),
        ).fetchone()
        # Behaviour.enabled is capability. Initial hierarchy activity is not.
        if not enabled:
            continue
        if rule in ("shivering_phantom_wards", "reliquary_wards"):
            ward_sources.add(source)
            continue
        if rule == "planning_portals":
            selections = planning[source] if planning is not None else _select_planning_portals(raw, conn, source)
            gates.extend(_planning_portal_gates(raw, source, selections))
            continue
        if rule == "npc_shout_essentials":
            gates.extend(_shout_essential_gates(raw, conn, source, host))
            continue
        identity = f"activation:{source}"
        if rule in {"astra_deaths", "stowaway_deaths"}:
            gates.extend(_death_trigger_gates(raw, conn, source, rule))
            continue
        if rule in {"fernalla_portal_wards", "morph_trigger"}:
            fields = ("Ward1", "Ward2", "Ward3") if rule == "fernalla_portal_wards" else ("Enable",)
            gates.extend(
                Gate(kind, key, identity, ((),), controller_source_key=source)
                for field in fields
                for kind, key in _scripted_targets(raw, conn, source, field, "enable", objects=True)
            )
            continue
        if rule == "bellwain_reveal":
            # code-fact: progression.bellwain.quest
            values = raw.execute(
                "SELECT value FROM code_facts WHERE fact_id = 'progression.bellwain.quest' AND key = 'quest'"
            ).fetchall()
            if len(values) != 1:
                raise ValueError(f"Missing Bellwain activation quest for {source}")
            quest = "quest:" + str(values[0][0]).lower()
            gates.extend(
                Gate(kind, key, identity, ((Atom("quest_done", quest),),), controller_source_key=source)
                for kind, key in _scripted_targets(raw, conn, source, "TheBellwains", "enable", objects=True)
            )
            continue
        if rule == "piety_guardians":
            quest = _scripted_reference(raw, source, "RequiredQuest", "quest")
            gates.extend(
                Gate(kind, key, identity, ((Atom("quest_not_done", quest),),), controller_source_key=source)
                for kind, key in _scripted_targets(raw, conn, source, "Guardians", "enable", objects=True)
            )
            continue
        if rule in restored:
            # code-fact: guide.gates.fernalla_reset
            # code-fact: guide.gates.fernalla_reveal
            # code-fact: guide.gates.soluna_reset
            # code-fact: guide.gates.soluna_reveal
            # code-fact: guide.gates.brax_reset
            # code-fact: guide.gates.brax_death
            # code-fact: guide.gates.brax_reveal
            field, spawn_field = restored[rule]
            spawn = _scripted_reference(raw, source, spawn_field, "spawn_point")
            groups = _spawn_encounter_groups(raw, conn, [spawn])
            identity += ":" + spawn
        elif rule == "restored_vitheo":
            # code-fact: guide.gates.vitheo_reveal
            rounds = raw.execute(
                "SELECT StableKey FROM ArenaRounds WHERE Scene = ? AND ArenaObjectName = ? AND RoundIndex = 8",
                (scene, object_name),
            ).fetchall()
            if len(rounds) != 1:
                raise ValueError(f"Missing or ambiguous final arena round for {source}")
            enemies = {
                Atom("encounter_won", key)
                for (key,) in raw.execute(
                    "SELECT EnemyCharacterStableKey FROM ArenaRoundEnemies WHERE ArenaRoundStableKey = ?",
                    (rounds[0][0],),
                )
            }
            if not enemies:
                raise ValueError(f"Missing final arena enemies for {source}")
            field, groups = "RestoredVitheo", _ordered_groups([enemies])
            identity += ":" + rounds[0][0]
        elif rule == "memory_sphere":
            # code-fact: guide.gates.memory_enter
            # code-fact: guide.gates.memory_exit
            field = "Memory"
            groups = ((Atom("item_held", _scripted_reference(raw, source, "RequiredInInventory", "item")),),)
        elif rule == "shivering_angel":
            # code-fact: guide.gates.angel
            field, groups = "$host", ((Atom("quest_done", "quest:standangel"),),)
        else:
            # code-fact: guide.gates.npc_alive
            # Only DespawnIfAlive subjects appear after the linked death.
            # SpawnIfAlive barriers need reviewed spatial guards, not guesses
            # about their children or nearby placements.
            targets = _scripted_targets(raw, conn, source, "DespawnIfAlive", "enable", objects=True)
            if not targets:
                continue
            spawn = _scripted_reference(raw, source, "SpawnPoint", "spawn_point")
            groups = _spawn_encounter_groups(raw, conn, [spawn])
            for kind, key in targets:
                gates.append(Gate(kind, key, identity + ":" + spawn, groups, controller_source_key=source))
            continue
        mode = "reference" if field == "$host" else "enable"
        gates.extend(
            Gate(kind, key, identity, groups, controller_source_key=source)
            for kind, key in _scripted_targets(raw, conn, source, field, mode, objects=field != "$host")
        )
    if ward_sources:
        gates.extend(_ward_gates(raw, conn, ward_sources))
    return gates


def _death_trigger_gates(raw: sqlite3.Connection, conn: sqlite3.Connection, source: str, rule: str) -> list[Gate]:
    if rule == "astra_deaths":
        # code-fact: progression.astra.death_set
        spawns = [
            key
            for (key,) in raw.execute(
                "SELECT ReferenceKey FROM ScriptedActivatorReferences"
                " WHERE SourceKey = ? AND Field = 'StarSpawns' AND ReferenceKind = 'spawn_point'"
                " ORDER BY ReferenceKey",
                (source,),
            )
        ]
        if not spawns:
            raise ValueError(f"Missing death trigger spawns for {source}")
        groups = _spawn_encounter_groups(raw, conn, spawns)
        character = _scripted_reference(raw, source, "Dragon", "character")
        targets = [
            ("spawn_point", key)
            for (key,) in raw.execute(
                "SELECT d.Key FROM DynamicCharacterSpawns d JOIN ScriptedActivators a"
                " ON a.ObjectKey = d.ControllerObjectKey"
                " WHERE a.SourceKey = ? AND d.CharacterStableKey = ? ORDER BY d.Key",
                (source, character),
            )
            if conn.execute("SELECT 1 FROM character_spawns WHERE spawn_point_stable_key = ?", (key,)).fetchone()
        ]
        if not targets:
            raise ValueError(f"Missing dynamic death-trigger spawn for {source}")
    else:
        # code-fact: progression.stowaway.death_set
        characters = {
            Atom("encounter_won", key)
            for (key,) in raw.execute(
                "SELECT ReferenceKey FROM ScriptedActivatorReferences WHERE SourceKey = ?"
                " AND Field = '$checkin_character' AND ReferenceKind = 'character'",
                (source,),
            )
        }
        if not characters:
            raise ValueError(f"Missing checked-in death trigger characters for {source}")
        groups = _ordered_groups([characters])
        targets = _scripted_targets(raw, conn, source, "KeeperSpawn", "enable", objects=True)
        if not targets:
            raise ValueError(f"Missing keeper activation target for {source}")
    return [Gate(kind, key, f"activation:{source}", groups, controller_source_key=source) for kind, key in targets]


def _select_planning_portals(
    raw: sqlite3.Connection, conn: sqlite3.Connection, source: str
) -> tuple[PlanningPortalSelection, ...]:
    """Resolve each exported portal once before projecting gates and slot roles."""
    selections: list[PlanningPortalSelection] = []
    mappings = [(field, (slot,), "dedicated", game_id) for field, slot, game_id in _PLANAR_PORTALS] + [
        (field, _RUNE_SLOTS, "rune", game_id) for field, game_id in _RUNE_PORTALS
    ]
    lines: set[str] = set()
    for field, slots, slot_kind, game_id in mappings:
        _scripted_reference(raw, source, field, "object")
        items = conn.execute("SELECT stable_key FROM items WHERE id = ?", (game_id,)).fetchall()
        if len(items) != 1:
            raise ValueError(f"Missing or ambiguous stored portal item {game_id} for {source}.{field}")
        targets = [
            (kind, key) for kind, key in _scripted_targets(raw, conn, source, field, "enable") if kind == "zone_line"
        ]
        exported_targets = raw.execute(
            "SELECT DISTINCT t.Kind, t.Key FROM ScriptedActivatorReferences r"
            " JOIN ScriptedActivatorTargets t ON t.ReferenceId = r.ReferenceId"
            " WHERE r.SourceKey = ? AND r.Field = ? AND t.ResolutionMode = 'enable' AND t.Kind = 'zone_line'",
            (source, field),
        ).fetchall()
        if len(exported_targets) != 1 or len(targets) != 1 or targets[0][0] != "zone_line":
            raise ValueError(f"Missing or ambiguous portal zone line for {source}.{field}")
        _, line = targets[0]
        destinations = conn.execute(
            "SELECT z.stable_key FROM zone_lines l"
            " JOIN zones z ON z.stable_key = l.destination_zone_stable_key WHERE l.stable_key = ?",
            (line,),
        ).fetchall()
        if len(destinations) != 1 or not destinations[0][0]:
            raise ValueError(f"Missing or ambiguous portal destination for {source}.{field}")
        if line in lines:
            raise ValueError(f"Missing or ambiguous distinct portal zone line for {source}.{field}")
        lines.add(line)
        selections.extend(
            PlanningPortalSelection(line, slot, slot_kind, items[0][0], destinations[0][0]) for slot in slots
        )
    return tuple(selections)


def _planning_portal_gates(
    raw: sqlite3.Connection, source: str, selections: tuple[PlanningPortalSelection, ...]
) -> list[Gate]:
    by_line: dict[str, list[PlanningPortalSelection]] = defaultdict(list)
    for selection in selections:
        by_line[selection.line].append(selection)
    fields = [field for field, _, _ in _PLANAR_PORTALS] + [field for field, _ in _RUNE_PORTALS]
    return [
        Gate(
            "object",
            _scripted_reference(raw, source, field, "object"),
            f"activation:planning_slot:{source}:{field}",
            tuple((Atom("planning_slot_item", selection.item_stable_key, selection.slot),) for selection in slots),
            controller_source_key=source,
        )
        for field, (line, slots) in zip(fields, by_line.items(), strict=True)
    ]


def _ward_gates(raw: sqlite3.Connection, conn: sqlite3.Connection, controllers: set[str]) -> list[Gate]:
    """Consume the producer's feasible branches without rebuilding eligibility."""
    # code-fact: guide.gates.phantom_host
    # code-fact: guide.gates.phantom_wards
    # code-fact: guide.gates.reliquary_sources
    # code-fact: guide.gates.reliquary_wards
    branches: dict[tuple[str, str, str], list[tuple[str, str, int, int]]] = defaultdict(list)
    for character, mechanism, source, kind, key, feasible, enabled in conn.execute(
        "SELECT character_stable_key, mechanism, source_stable_key, condition_kind,"
        " condition_stable_key, can_release, controller_enabled FROM character_damage_releases"
        " WHERE mechanism IN ('shivering_phantom_wards', 'reliquary_wards')"
        " ORDER BY character_stable_key, mechanism, source_stable_key, condition_kind, condition_stable_key"
    ):
        branches[(character, mechanism, source)].append((kind, key, feasible, enabled))
    groups: dict[tuple[str, str], list[set[Atom]]] = defaultdict(list)
    selectors: dict[tuple[str, str], set[str]] = defaultdict(set)
    for (character, mechanism, source), conditions in branches.items():
        if any(not feasible or not enabled for _, _, feasible, enabled in conditions):
            continue
        if mechanism == "shivering_phantom_wards":
            if source not in controllers:
                continue
            subject = ("character", character)
        else:
            if not any(kind == "controller" and key in controllers for kind, key, _, _ in conditions):
                continue
            if (
                conn.execute(
                    "SELECT 1 FROM character_spawns WHERE character_stable_key = ? AND spawn_point_stable_key = ?",
                    (character, source),
                ).fetchone()
                is None
            ):
                continue
            subject = ("spawn_point", source)
        # Linked deaths are one conjunction. Different release sources are OR.
        spawns = [key for kind, key, _, _ in conditions if kind == "spawn_point_cleared"]
        direct = {Atom("encounter_won", key) for kind, key, _, _ in conditions if kind == "character_dead"}
        groups[subject].extend(set(group) | direct for group in _spawn_encounter_groups(raw, conn, spawns))
        selectors[subject].update((source, *spawns))
        selectors[subject].update(key for kind, key, _, _ in conditions if kind == "controller")
    return [
        Gate(kind, key, "damage_release:" + "|".join(sorted(selectors[(kind, key)])), _ordered_groups(alternatives))
        for (kind, key), alternatives in sorted(groups.items())
        # A branch with no wards needs no prerequisite.
        if all(alternatives)
    ]


def _shout_essential_gates(raw: sqlite3.Connection, conn: sqlite3.Connection, source: str, host: str) -> list[Gate]:
    # code-fact: guide.gates.shout_essential_block
    # code-fact: guide.gates.shout_essentials
    # code-fact: guide.gates.shout_completion
    flags = raw.execute(
        "SELECT ReferenceKind, BoolValue FROM ScriptedActivatorReferences WHERE SourceKey = ?"
        " AND Field = 'UseEssentialSpawnsToBlockThisInstance'",
        (source,),
    ).fetchall()
    if len(flags) != 1 or flags[0][0] != "bool" or flags[0][1] not in (0, 1):
        raise ValueError(f"Missing or ambiguous essential-spawn flag for {source}")
    if not flags[0][1]:
        return []
    gates = []
    for (spawn,) in raw.execute(
        "SELECT DISTINCT SpawnPointStableKey FROM SpawnPointCharacters WHERE CharacterStableKey = ? ORDER BY 1",
        (host,),
    ):
        if (
            conn.execute(
                "SELECT 1 FROM character_spawns WHERE character_stable_key = ? AND spawn_point_stable_key = ?",
                (host, spawn),
            ).fetchone()
            is None
        ):
            continue
        wards = [
            ward
            for (ward,) in raw.execute(
                "SELECT EssentialSpawnPointStableKey FROM SpawnPointEssentialLinks"
                " WHERE SourceSpawnPointStableKey = ? ORDER BY EssentialSpawnPointStableKey",
                (spawn,),
            )
        ]
        if wards:
            identity = "shout_essentials:" + "|".join((source, spawn, *wards))
            gates.append(Gate("spawn_point", spawn, identity, _spawn_encounter_groups(raw, conn, wards)))
    return gates


def _spawn_encounter_groups(
    raw: sqlite3.Connection, conn: sqlite3.Connection, spawns: list[str]
) -> tuple[tuple[Atom, ...], ...]:
    """AND required spawn points, OR each point's exported character choices."""
    groups: list[Counter[str]] = [Counter()]
    for spawn in sorted(set(spawns)):
        characters = [
            key
            for (key,) in raw.execute(
                "SELECT DISTINCT CharacterStableKey FROM SpawnPointCharacters"
                " WHERE SpawnPointStableKey = ? ORDER BY CharacterStableKey",
                (spawn,),
            )
            if conn.execute("SELECT 1 FROM characters WHERE stable_key = ?", (key,)).fetchone() is not None
        ]
        if not characters:
            raise ValueError(f"No guide character candidates for required encounter spawn {spawn!r}")
        groups = [group + Counter({character: 1}) for group in groups for character in characters]
    return _ordered_groups(
        [
            {
                Atom("encounter_won", character, quantity=count if count > 1 else None)
                for character, count in group.items()
            }
            for group in groups
        ]
    )


def _shiver_event_gates(raw: sqlite3.Connection, conn: sqlite3.Connection) -> list[Gate]:
    """Apply the event's re-entry phases to the referenced placements."""
    # code-fact: guide.gates.shiver_start
    # code-fact: guide.gates.shiver_update
    # code-fact: guide.gates.shiver_init
    before_keepers = tuple((Atom("quest_not_done", quest),) for quest in SHIVER_KEEPER_QUESTS)
    after_keepers = tuple(Atom("quest_done", quest) for quest in SHIVER_KEEPER_QUESTS)
    rules = {
        "FirstKio": (before_keepers, "disable"),
        "WelcomeCrew": (before_keepers, "disable"),
        "Kio": (((*after_keepers, Atom("quest_not_done", "quest:shiver-lighthousechange")),), "enable"),
        "Hider": (
            ((Atom("quest_done", "quest:shiver-torch"), Atom("quest_not_done", "quest:shiver-flamelit")),),
            "enable",
        ),
        "SpawnTriggers": (((Atom("quest_done", "quest:shiver-torch"),),), "enable"),
        "Phantom": (((Atom("quest_done", "quest:shiver-glasses"),),), "enable"),
        "WarmFlame": (((Atom("quest_done", "quest:shiver-flamelit"),),), "enable"),
    }
    gates: list[Gate] = []
    for source, field, mode, kind, key in raw.execute(
        "SELECT DISTINCT a.SourceKey, r.Field, t.ResolutionMode, t.Kind, t.Key"
        " FROM ScriptedActivators a"
        " JOIN ScriptedActivatorReferences r ON r.SourceKey = a.SourceKey"
        " JOIN ScriptedActivatorTargets t ON t.ReferenceId = r.ReferenceId"
        " WHERE a.RuleId = 'shiver_event' AND a.ComponentIsEnabled = 1 ORDER BY 1, 2, 3, 4, 5"
    ):
        rule = rules.get(field)
        if rule is None or mode != rule[1]:
            continue
        if kind == "object":
            identity = f"activation:{source}:{field}" if mode == "enable" else f"shiver_event:{source}:{field}"
            gates.append(Gate(kind, key, identity, rule[0], controller_source_key=source))
            continue
        if kind not in _TARGET_TABLES:
            continue
        table, column = _TARGET_TABLES[kind]
        if conn.execute(f"SELECT 1 FROM {table} WHERE {column} = ?", (key,)).fetchone() is not None:
            gates.append(Gate(kind, key, f"shiver_event:{source}:{field}", rule[0]))
    return gates


def _shiver_event_quest_sources(raw: sqlite3.Connection, writer: Writer) -> None:
    """Keep the event's four subquests in the parent's completion checklist."""
    # code-fact: guide.gates.shiver_update
    # code-fact: guide.gates.shiver_init
    scenes = [
        scene
        for (scene,) in raw.execute("SELECT DISTINCT SourceScene FROM ScriptedActivators WHERE RuleId = 'shiver_event'")
    ]
    if not scenes:
        return
    conn = writer.conn
    conn.execute(
        "UPDATE quests SET step_note = ? WHERE stable_key = 'quest:shiver-hider'",
        ("Wait for darkness, which begins ten seconds after completing The Shivering Torch.",),
    )
    conn.execute("DELETE FROM quest_completion_sources WHERE quest_stable_key = ?", (SHIVER_MEET_ALL,))
    writer.insert_quest_completion_sources(
        [
            {
                "quest_stable_key": SHIVER_MEET_ALL,
                "method": "chain",
                "source_type": "quest",
                "source_stable_key": quest,
            }
            for quest in SHIVER_KEEPER_QUESTS
        ]
    )
    conn.execute("DELETE FROM quest_acquisition_sources WHERE quest_stable_key = ?", (SHIVER_MEET_ALL,))
    acquisition: list[dict[str, object]] = []
    for scene in scenes:
        zone = conn.execute("SELECT stable_key FROM zones WHERE scene_name = ?", (scene,)).fetchone()
        if zone is None:
            raise ValueError(f"ShiverEvent scene {scene!r} has no zone for its quest acquisition")
        acquisition.append(
            {
                "quest_stable_key": SHIVER_MEET_ALL,
                "method": "zone_entry",
                "source_type": "zone",
                "source_stable_key": zone[0],
                "note": None,
            }
        )
    for quest, previous, note in (
        ("quest:shiver-torch", SHIVER_MEET_ALL, "Assigned after meeting all four keepers."),
        ("quest:shiver-hider", "quest:shiver-torch", None),
    ):
        conn.execute(
            "DELETE FROM quest_acquisition_sources WHERE quest_stable_key = ? AND method = 'scripted'", (quest,)
        )
        acquisition.append(
            {
                "quest_stable_key": quest,
                "method": "quest_chain",
                "source_type": "quest",
                "source_stable_key": previous,
                "note": note,
            }
        )
    writer.insert_quest_acquisition_sources(acquisition)


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
        " WHERE quest_stable_key IS NOT NULL AND NOT EXISTS"
        " (SELECT 1 FROM character_vendor_items base WHERE base.character_stable_key=copy_stable_key"
        " AND base.item_stable_key=vendor_offers.item_stable_key)"
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
    # code-fact: guide.gates.door_key
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
        "planning_slot_item": items,
        "encounter_won": {key for (key,) in conn.execute("SELECT stable_key FROM characters")},
    }
    for gate in gates:
        for group in gate.groups:
            for atom in group:
                if atom.quantity is not None and (atom.kind != "encounter_won" or atom.quantity < 1):
                    raise ValueError(f"{gate.gate} has an invalid defeat quantity {atom.quantity!r}")
                if atom.kind == "planning_slot_item" and atom.slot not in _PLANNING_SLOTS:
                    raise ValueError(f"{gate.gate} names unknown stored planning slot {atom.slot!r}")
                if atom.kind in known and atom.stable_key not in known[atom.kind]:
                    raise ValueError(
                        f"{gate.gate} gate on {gate.subject_stable_key!r} names unknown {atom.kind} {atom.stable_key!r}"
                    )


def _atom_order(atom: Atom) -> tuple[str, str, str, int]:
    return (atom.kind, atom.stable_key, atom.slot or "", atom.quantity or 1)


def _ordered_groups(groups: Iterable[set[Atom]]) -> tuple[tuple[Atom, ...], ...]:
    ordered = {tuple(sorted(group, key=_atom_order)) for group in groups}
    return tuple(sorted(ordered, key=lambda group: [_atom_order(atom) for atom in group]))
