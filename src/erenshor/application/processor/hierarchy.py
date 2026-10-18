"""Project scene activity and controller effects onto their exported subjects."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .gates import CONTROLLER, Atom, Gate, _ordered_groups
from .planning import _ROOM_SLOTS

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable, Iterable

Groups = tuple[tuple[Atom, ...], ...]
_TRUE: Groups = ((),)
_FALSE: Groups = ()


@dataclass(frozen=True, slots=True)
class _Effect:
    groups: Groups
    host: str | None = None
    controller: str | None = None


@dataclass(frozen=True, slots=True)
class Activity:
    """Resolved scene activity.

    ``gates`` are the subject gates. ``host`` and ``controller`` say when an
    object is active and when a controller's effects can happen, both before
    any removal, because a mechanism needs its controller before it acts.
    """

    gates: list[Gate]
    host: Callable[[str], Groups]
    controller: Callable[[str], Groups]


def _simplify(groups: Iterable[Iterable[Atom]]) -> Groups:
    choices: set[frozenset[Atom]] = set()
    for group in groups:
        atoms: dict[tuple[str, str, str | None], Atom] = {}
        for atom in group:
            identity = (atom.kind, atom.stable_key, atom.slot)
            previous = atoms.get(identity)
            if previous is None or (atom.quantity or 1) > (previous.quantity or 1):
                atoms[identity] = atom
        choices.add(frozenset(atoms.values()))
    choices = {
        group
        for group in choices
        if not any(atom.kind == "never" for atom in group)
        and not any(
            Atom("quest_not_done" if atom.kind == "quest_done" else "quest_done", atom.stable_key) in group
            for atom in group
            if atom.kind in {"quest_done", "quest_not_done"}
        )
    }
    return _ordered_groups([set(group) for group in choices if not any(other < group for other in choices)])


def _and(left: Groups, right: Groups) -> Groups:
    return _simplify((*first, *second) for first in left for second in right)


def _inverse(groups: Groups, source: str) -> Groups:
    result = _TRUE
    for group in groups:
        alternatives = []
        for atom in group:
            if atom.kind not in {"quest_done", "quest_not_done"}:
                raise ValueError(f"{source} has a removal atom without an inverse: {atom.kind}")
            alternatives.append(
                (Atom("quest_not_done" if atom.kind == "quest_done" else "quest_done", atom.stable_key),)
            )
        result = _and(result, tuple(alternatives))
    return result


def apply_hierarchy_activity(raw: sqlite3.Connection, conn: sqlite3.Connection, gates: list[Gate]) -> Activity:
    """Resolve availability from initial activity, activation effects, and parents.

    A least fixed point prevents controllers inside an inactive subtree from
    enabling themselves without a reachable activator.
    """
    objects = {
        key: (parent, bool(active), bool(scene_object))
        for key, parent, active, scene_object in raw.execute(
            "SELECT ObjectKey, ParentObjectKey, ActiveSelf, IsSceneObject FROM ObjectHierarchy"
        )
    }
    for key, (parent, _, _) in objects.items():
        if parent is not None and parent not in objects:
            raise ValueError(f"ObjectHierarchy lacks ancestor {parent!r} of {key!r}")
        trail = {key}
        ancestor = parent
        while ancestor is not None:
            if ancestor in trail:
                raise ValueError(f"ObjectHierarchy has a parent cycle at {ancestor!r}")
            trail.add(ancestor)
            ancestor = objects[ancestor][0]

    subjects: dict[tuple[str, str], str] = {}
    components: dict[tuple[str, str], bool] = {}
    specifications = (
        ("Characters", "StableKey", "character", "characters", "stable_key"),
        ("SpawnPoints", "StableKey", "spawn_point", "character_spawns", "spawn_point_stable_key"),
        ("SpawnPointTriggers", "StableKey", "spawn_point", "character_spawns", "spawn_point_stable_key"),
        ("ZoneLines", "StableKey", "zone_line", "zone_lines", "stable_key"),
        ("ItemBags", "StableKey", "item_bag", "item_bags", "stable_key"),
        ("Doors", "StableKey", "door", "doors", "stable_key"),
        ("UiItemAccessTargets", "StableKey", "ui_item_access_target", "ui_item_access_targets", "stable_key"),
    )
    for raw_table, raw_key, kind, clean_table, clean_key in specifications:
        present = {key for (key,) in conn.execute(f"SELECT DISTINCT {clean_key} FROM {clean_table}")}
        # A placed Character's disabled behaviour is not proof that its NPC is
        # unavailable. SpawnPoint.Update, unlike those external NPC calls,
        # requires the spawn component to run.
        component_column = (
            "CASE WHEN IsDirectlyPlaced = 0 THEN ComponentIsEnabled ELSE 1 END" if raw_table == "SpawnPoints" else "1"
        )
        for key, object_key, component in raw.execute(
            f"SELECT {raw_key}, ObjectKey, {component_column} FROM {raw_table}"
        ):
            if object_key not in objects:
                raise ValueError(f"{raw_table} {key!r} names missing hierarchy object {object_key!r}")
            if key in present and objects[object_key][2]:
                subjects[kind, key] = object_key
                components[kind, key] = bool(component)

    controllers = {
        source: (object_key, bool(enabled))
        for source, object_key, enabled in raw.execute(
            "SELECT SourceKey, ObjectKey, ComponentIsEnabled FROM ScriptedActivators"
        )
    }
    # Effects that enable a controller's disabled behaviour, such as JawsStatueStartup.
    enablers: dict[str, list[_Effect]] = defaultdict(list)
    dynamic = {
        key: (character, controller, bool(component))
        for key, character, controller, component in raw.execute(
            "SELECT Key, CharacterStableKey, ControllerObjectKey, ControllerComponentIsEnabled"
            " FROM DynamicCharacterSpawns"
        )
    }
    chained_hosts: dict[str, set[str]] = defaultdict(set)
    for parent, child, script, controller, component in raw.execute(
        "SELECT ParentStableKey, ChildStableKey, SourceScript, ControllerObjectKey, ControllerComponentIsEnabled"
        " FROM CharacterChainedSpawns"
    ):
        for key, parent_spawn in conn.execute(
            "SELECT child.spawn_point_stable_key, parent.spawn_point_stable_key"
            " FROM character_spawns child JOIN character_spawns parent"
            " ON parent.character_stable_key = ? AND parent.scene = child.scene"
            " AND parent.x IS child.x AND parent.y IS child.y AND parent.z IS child.z"
            " WHERE child.character_stable_key = ? AND child.source_script = ? AND child.is_trigger_spawn = 1",
            (parent, child, script),
        ):
            dynamic[key] = (child, controller, bool(component))
            parent_object = parent_spawn or subjects.get(("character", parent))
            if parent_object is not None:
                chained_hosts[key].add(parent_object)
    for key, (_, controller, _) in dynamic.items():
        if controller not in objects:
            raise ValueError(f"Dynamic spawn {key!r} lacks controller object {controller!r}")

    intrinsic: dict[str, Groups] = defaultdict(lambda: _TRUE)
    for subject, component in components.items():
        if not component:
            intrinsic[subjects[subject]] = _FALSE
    enabled: dict[str, list[_Effect]] = defaultdict(list)
    disabled: dict[str, list[tuple[str, _Effect]]] = defaultdict(list)
    dynamic_conditions: dict[str, Groups] = defaultdict(lambda: _TRUE)
    object_conditions: dict[str, Groups] = defaultdict(lambda: _TRUE)
    result: list[Gate] = []
    # code-fact: planning.build_gate
    # code-fact: planning.build_furnishing
    furnishings = {
        name: item
        for item, name in conn.execute("SELECT stable_key, equipment_to_activate FROM items WHERE furniture_set = 1")
    }
    for object_key, controller, slot, furnishing in raw.execute(
        "SELECT ObjectKey, ControllerObjectKey, Slot, Furnishing FROM PlanningTableFurnishings"
    ):
        if slot in _ROOM_SLOTS and furnishing in furnishings:
            enabled[object_key].append(
                _Effect(((Atom("room_furnished", furnishings[furnishing], slot),),), host=controller)
            )
    # code-fact: guide.gates.reliquary_return_portal
    # A stored-return listener enables its portal whenever the character has a
    # saved return. That state lives in the line's destination context, so the
    # portal itself needs only its controller's host.
    for source, portal in raw.execute(
        "SELECT a.SourceKey, r.ReferenceKey FROM ScriptedActivators a"
        " JOIN ScriptedActivatorReferences r ON r.SourceKey = a.SourceKey AND r.Field = 'ReliqPort'"
        " WHERE a.RuleId = 'reliquary_return_portal' AND a.ComponentIsEnabled = 1"
    ):
        if portal not in objects or source not in controllers:
            raise ValueError(f"Stored return controller {source!r} has no hierarchy portal {portal!r}")
        enabled[portal].append(_Effect(_TRUE, host=controllers[source][0]))
    for gate in gates:
        if gate.subject_kind == CONTROLLER:
            if gate.subject_stable_key not in controllers:
                raise ValueError(f"{gate.gate} enables missing controller {gate.subject_stable_key!r}")
            enabled_by = _Effect(gate.groups, controller=gate.controller_source_key)
            enablers[gate.subject_stable_key].append(enabled_by)
            continue
        subject = (gate.subject_kind, gate.subject_stable_key)
        object_key = gate.subject_stable_key if gate.subject_kind == "object" else subjects.get(subject)
        if gate.gate.startswith("activation"):
            if gate.subject_kind == "spawn_point" and gate.subject_stable_key in dynamic:
                dynamic_conditions[gate.subject_stable_key] = _and(
                    dynamic_conditions[gate.subject_stable_key], gate.groups
                )
                continue
            if object_key is None:
                # An excluded placement has no consumer in this build.
                continue
            if object_key not in objects:
                raise ValueError(f"{gate.gate} names missing hierarchy object {object_key!r}")
            enabled[object_key].append(_Effect(gate.groups, controller=gate.controller_source_key))
        else:
            if gate.subject_kind == "object":
                object_conditions[gate.subject_stable_key] = _and(
                    object_conditions[gate.subject_stable_key], gate.groups
                )
                continue
            result.append(gate)
            if object_key is not None and gate.gate in {"spawn_start", "spawn_stop", "furnishing"}:
                intrinsic[object_key] = _and(intrinsic[object_key], gate.groups)
            if object_key is not None and gate.gate.startswith("shiver_event:"):
                enabled[object_key].append(_Effect(gate.groups))
                intrinsic[object_key] = _and(intrinsic[object_key], gate.groups)

    effects: dict[tuple[str, str, str, int], set[Atom]] = defaultdict(set)
    hosts: dict[str, str] = {}
    for target, effect, listener, host, component_enabled, group, kind, key in raw.execute(
        "SELECT TargetObjectKey, Effect, ListenerKey, ListenerObjectKey, ListenerComponentIsEnabled,"
        " GroupIndex, AtomKind, AtomStableKey FROM QuestActivationEffects"
    ):
        if not component_enabled:
            continue
        if target not in objects or host not in objects:
            raise ValueError(f"{listener} has a missing target or controller hierarchy object")
        if effect not in {"enable", "disable"} or kind not in {"quest_done", "item_held", "encounter_won"}:
            raise ValueError(f"{listener} has unknown activation {effect!r}/{kind!r}")
        hosts[listener] = host
        effects[target, effect, listener, group].add(Atom(kind, key))
    for (target, effect, listener, _), atoms in effects.items():
        groups = _ordered_groups([atoms])
        if effect == "enable":
            enabled[target].append(_Effect(groups, host=hosts[listener]))
        else:
            disabled[target].append((listener, _Effect(groups, host=hosts[listener])))

    placements: dict[str, set[str]] = defaultdict(set)
    for character, spawn in conn.execute("SELECT character_stable_key, spawn_point_stable_key FROM character_spawns"):
        if spawn is not None:
            placements[character].add(spawn)
        elif ("character", character) in subjects:
            placements[character].add(subjects["character", character])
    spawn_objects = {key: obj for (kind, key), obj in subjects.items() if kind == "spawn_point"}
    object_characters: dict[str, set[str]] = defaultdict(set)
    for character, obj in raw.execute("SELECT StableKey, ObjectKey FROM Characters"):
        object_characters[obj].add(character)

    def placement_groups(placement: str, current: dict[str, Groups], spawned: dict[str, Groups]) -> Groups:
        if placement in spawned:
            return spawned[placement]
        obj = spawn_objects.get(placement, placement)
        if obj not in current:
            return _FALSE
        return _and(current[obj], intrinsic[obj])

    def host_groups(object_key: str, current: dict[str, Groups], spawned: dict[str, Groups]) -> Groups:
        if object_key not in objects:
            raise ValueError(f"Controller names missing hierarchy object {object_key!r}")
        if objects[object_key][2]:
            return _and(current[object_key], intrinsic[object_key])
        characters = object_characters[object_key]
        if not characters:
            return current[object_key]
        alternatives: list[tuple[Atom, ...]] = []
        for character in characters:
            for placement in placements[character]:
                alternatives.extend(placement_groups(placement, current, spawned))
        return _simplify(alternatives)

    def controller_groups(
        source: str, current: dict[str, Groups], spawned: dict[str, Groups], trail: frozenset[str] = frozenset()
    ) -> Groups:
        """When a controller can act: its host is active and its behaviour is enabled."""
        if source not in controllers:
            raise ValueError(f"Missing scripted controller {source!r}")
        object_key, enabled = controllers[source]
        host = host_groups(object_key, current, spawned)
        if enabled:
            return host
        # A disabled behaviour runs only after an enabler enables it.
        alternatives = [
            group
            for effect in enablers[source]
            if effect.controller is not None and effect.controller not in trail
            for group in _and(effect.groups, controller_groups(effect.controller, current, spawned, trail | {source}))
        ]
        return _and(host, _simplify(alternatives))

    def solve(removals: dict[str, Groups]) -> tuple[dict[str, Groups], dict[str, Groups]]:
        current: dict[str, Groups] = dict.fromkeys(objects, _FALSE)
        spawned: dict[str, Groups] = dict.fromkeys(dynamic, _FALSE)
        for _ in range(len(objects) + len(dynamic) + 1):
            updated: dict[str, Groups] = {}
            for key, (parent, active, _) in objects.items():
                alternatives = list(_TRUE if active else _FALSE)
                for effect in enabled[key]:
                    required = _TRUE
                    if effect.host is not None:
                        required = host_groups(effect.host, current, spawned)
                    if effect.controller is not None:
                        required = controller_groups(effect.controller, current, spawned)
                    alternatives.extend(_and(effect.groups, required))
                available = _and(_simplify(alternatives), object_conditions[key])
                available = _and(available, removals.get(key, _TRUE))
                updated[key] = _and(available, current[parent]) if parent is not None else available
            updated_spawns = {}
            for key, (_, controller, component) in dynamic.items():
                if not component:
                    updated_spawns[key] = _FALSE
                    continue
                host = (
                    _simplify(
                        group
                        for placement in chained_hosts[key]
                        for group in placement_groups(placement, current, spawned)
                    )
                    if key in chained_hosts
                    else host_groups(controller, current, spawned)
                )
                updated_spawns[key] = _and(host, dynamic_conditions[key])
            if updated == current and updated_spawns == spawned:
                return updated, updated_spawns
            current, spawned = updated, updated_spawns
        raise ValueError("Object activity did not reach a fixed point")

    # A removal needs its controller before the effect. A listener may remove
    # its own host, so post-removal activity cannot be that prerequisite.
    reachable, reachable_spawns = solve({})
    removals: dict[str, Groups] = {}
    for key, removal_effects in disabled.items():
        remaining = _TRUE
        for listener, removal in removal_effects:
            host = host_groups(removal.host, reachable, reachable_spawns) if removal.host is not None else _TRUE
            remaining = _and(remaining, _inverse(_and(removal.groups, host), listener))
        removals[key] = remaining
    values, dynamic_values = solve(removals)

    for (kind, key), object_key in sorted(subjects.items()):
        groups = values[object_key] if components[kind, key] else _FALSE
        if groups != _TRUE:
            result.append(Gate(kind, key, "activation:" + object_key, groups or ((Atom("never", object_key),),)))
    clean_spawns = {key for (key,) in conn.execute("SELECT DISTINCT spawn_point_stable_key FROM character_spawns")}
    for key, groups in sorted(dynamic_values.items()):
        if key in clean_spawns and groups != _TRUE:
            result.append(
                Gate("spawn_point", key, "activation:controller", groups or ((Atom("never", dynamic[key][0]),),))
            )
    return Activity(
        result,
        host=lambda object_key: host_groups(object_key, reachable, reachable_spawns),
        controller=lambda source: controller_groups(source, reachable, reachable_spawns),
    )
