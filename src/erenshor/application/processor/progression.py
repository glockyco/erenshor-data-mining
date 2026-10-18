"""Derive shared requirements and a new-character playthrough from clean facts."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from time import perf_counter
from typing import Any

from loguru import logger

from erenshor.domain.value_objects.item_provenance import condition_from_dict
from erenshor.domain.value_objects.progression import PROGRESSION_SCHEMA_VERSION

EXPANSION_LIMIT = 32
START_SCENE_FACTS = {
    "progression.new_character_scene": "mechanic:new_character_start",
    "progression.alternate_start_scene": "mechanic:alternate_start",
}

ACQUISITION_RELATIONS = {
    "character_drop": "drops",
    "vendor": "sells",
    "dialog": "gives",
    "quest_reward": "reward",
    "crafting": "mold",
    "mining": "mined in",
    "fishing": "fished in",
    "fishing_bonus": "fished in",
    "item_bag": "found in",
    "item_drop": "contained in",
    "spell_created": "created by",
    "item_conversion": "converted from",
    "special_world_drop": "from",
    "common_world_item": "from",
    "starting_class": "from",
    "ui_grant": "from",
}
ROUTE_RELATIONS = {
    "start": {
        "dialog": "talk to",
        "quest_chain": "after",
        "item_read": "read",
        "zone_entry": "enter",
        "partial_turnin": "turn in to",
        "scripted": "event",
    },
    "completion": {
        "item_turnin": "turn in to",
        "talk": "talk to",
        "read": "read",
        "death": "defeat",
        "zone": "enter",
        "shout": "hear",
        "chain": "after",
        "scripted": "event",
    },
}
_ATOM_RELATIONS = {
    "quest_done": "quest done",
    "quest_active": "quest active",
    "quest_not_done": "quest not done",
    "key_held": "key",
    "item_held": "held",
    "planning_slot_item": "planning slot",
    "room_furnished": "room furnished",
    "encounter_won": "defeated",
    "account_state": "state",
    "zone_use": "in zone",
    "world_state": "state",
}
_SOURCE_PROPERTIES = frozenset(
    {
        "item_not_owned",
        "actor_level",
        "actor_class",
        "time_of_day",
        "quality",
        "formula_operand",
        "route",
        "source_replenishment",
    }
)
_RELEASE_MECHANISMS = frozenset(
    {
        "trade_turn_in",
        "shivering_phantom_wards",
        "combat_ward_cycle",
        "reliquary_wards",
        "npc_protector_weather",
        "health_phase_timer",
        "spawn_health_phase_timer",
        "combat_empty_wards",
        "npc_protector_null",
        "npc_protector_inactive",
    }
)
_GATE_TREATMENTS = {
    "activation": "placement",
    "removal": "placement",
    "shiver_event": "placement",
    "shout_essentials": "placement",
    "spawn_start": "placement",
    "spawn_stop": "placement",
    "furnishing": "placement",
    "vendor_unlock": "placement",
    # Barriers other than doors are named by their first object.
    "object": "barrier",
    "door": "barrier",
    # _ward_gates derives vulnerability gates from character_damage_releases.
    "damage_release": "vulnerability",
}

_GATE_RELATIONS = frozenset(
    {
        "barrier",
        "quest done",
        "quest active",
        "quest not done",
        "key",
        "held",
        "planning slot",
        "room furnished",
        "defeated",
        "state",
        "summoned with",
        "release",
    }
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class Need:
    relation: str
    need_stable_key: str | None = None
    quantity: float | None = None
    slot: str | None = None
    keywords: str | None = None
    condition_key: str | None = None
    advisory: bool = False
    unconfirmed: bool = False
    required_level: int | None = None


Way = tuple[Need, ...]


def canonical_way(needs: tuple[Need, ...] | list[Need]) -> Way:
    return tuple(sorted(set(needs), key=lambda need: _json(asdict(need))))


def way_key(way: Way) -> str:
    return hashlib.sha256(_json([asdict(need) for need in way]).encode()).hexdigest()[:16]


def _error(node: str, fact: str, message: str, way: str = "deriving") -> ValueError:
    return ValueError(f"Progression node {node}, way {way}, fact {fact}: {message}")


class ProgressionBuilder:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.kinds: dict[str, str] = {}
        self.ways: dict[str, dict[str, Way]] = defaultdict(dict)
        self.milestones: set[str] = set()
        self.tiers: dict[str, int] = {}
        self.depths: dict[str, int] = {}
        self.first: dict[str, str] = {}
        self.ranks: dict[tuple[str, str], tuple[int, int]] = {}
        self.facts: dict[tuple[str, str], set[str]] = defaultdict(set)
        self.scenes = {row["scene_name"]: row["stable_key"] for row in self.rows("zones")}
        self.characters = {row["stable_key"]: row for row in self.rows("characters")}
        self.placements: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.occupants: dict[str, set[str]] = defaultdict(set)
        for row in self.rows("character_spawns"):
            self.placements[row["character_stable_key"]].append(row)
            if row["spawn_point_stable_key"]:
                self.occupants[row["spawn_point_stable_key"]].add(row["character_stable_key"])
        self.lines = {row["stable_key"]: row for row in self.rows("zone_lines")}
        self.slots = {
            (row["zone_line_stable_key"], row["slot"]): row["slot_kind"] for row in self.rows("planning_portal_slots")
        }
        self.gates: dict[tuple[str, str, str | None], list[dict[str, Any]]] = defaultdict(list)
        self.barriers: dict[str, list[dict[str, Any]]] = {}
        barrier_keys = {row["barrier_key"] for row in self.rows("barriers")}
        for row in self.rows("gate_conditions"):
            gate_kind = row["gate"].split(":", 1)[0]
            if gate_kind not in _GATE_TREATMENTS:
                raise _error(row["subject_stable_key"], row["gate"], f"unmapped gate kind {gate_kind!r}")
            if (_GATE_TREATMENTS[gate_kind] == "barrier") != (row["gate"] in barrier_keys):
                raise _error(row["subject_stable_key"], row["gate"], "barrier gate without its barrier record")
            self.gates[row["subject_kind"], row["subject_stable_key"], row["item_stable_key"]].append(row)
            if row["gate"] in barrier_keys:
                prior = self.barriers.setdefault(row["gate"], [])
                atom = {key: row[key] for key in ("gate", "group_index", "atom_kind", "atom_stable_key", "atom_slot")}
                if atom not in prior:
                    prior.append(atom)
            if row["atom_kind"] not in {*_ATOM_RELATIONS, "never"}:
                raise _error(row["subject_stable_key"], row["gate"], f"unmapped atom kind {row['atom_kind']!r}")
        self.entries: dict[tuple[str, str], set[str]] = defaultdict(set)
        for row in self.rows("target_entries"):
            self.entries[row["target_kind"], row["target_stable_key"]].add(row["zone_line_stable_key"])
        self.required: dict[str, list[Need]] = defaultdict(list)
        for row in self.rows("quest_required_items"):
            self.required[row["quest_variant_resource_name"]].append(
                Need("required item", row["item_stable_key"], quantity=row["quantity"], slot=str(row["required_slot"]))
            )
        self.releases: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for row in self.rows("character_damage_releases"):
            if row["mechanism"] not in _RELEASE_MECHANISMS:
                raise _error(
                    row["character_stable_key"],
                    row["source_stable_key"],
                    f"unmapped release mechanism {row['mechanism']!r}",
                )
            self.releases[row["character_stable_key"]][row["mechanism"], row["source_stable_key"]].append(row)
        self.acquisition_conditions = self.index("item_acquisition_conditions", "owner_key")
        self.locations = self.index("item_acquisition_locations", "owner_key")
        self.route_conditions = self.index("quest_route_conditions", "route_key")
        self.kill_cache: dict[str, list[Way]] = {}

    def rows(self, table: str) -> list[dict[str, Any]]:
        if table not in self.tables:
            cursor = self.connection.execute(f"SELECT * FROM {table}")
            columns = [column[0] for column in cursor.description]
            self.tables[table] = [dict(zip(columns, row, strict=True)) for row in cursor]
        return self.tables[table]

    def index(self, table: str, column: str) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self.rows(table):
            result[row[column]].append(row)
        return result

    def node(self, key: str, kind: str) -> None:
        if key in self.kinds and self.kinds[key] != kind:
            raise _error(key, "node identity", f"conflicting kinds {self.kinds[key]} and {kind}")
        self.kinds[key] = kind

    def add(self, node: str, needs: Way | list[Need], fact: str) -> None:
        way = canonical_way(needs)
        key = way_key(way)
        if node not in self.kinds:
            raise _error(node, fact, "subject resolves to no node", key)
        for need in way:
            if need.need_stable_key is not None and need.need_stable_key not in self.kinds:
                raise _error(node, fact, f"need resolves to no node: {need.need_stable_key}", key)
            if need.need_stable_key is None and need.condition_key is None:
                raise _error(node, fact, "need has neither a node nor a condition key", key)
        if key in self.ways[node] and self.ways[node][key] != way:
            raise _error(node, fact, "way digest collision", key)
        self.ways[node][key] = way
        self.facts[node, key].add(fact)

    def product(self, node: str, left: list[Way], right: list[Way], fact: str) -> list[Way]:
        result = {canonical_way((*a, *b)) for a in left for b in right}
        if len(result) > EXPANSION_LIMIT:
            raise _error(node, fact, f"gate expansion exceeds {EXPANSION_LIMIT} ways")
        return sorted(result, key=way_key)

    def atom(
        self,
        node: str,
        kind: str,
        key: str | None,
        slot: str | None,
        fact: str,
        value: str | None = None,
        quantity: float | None = None,
    ) -> list[Way]:
        if kind == "never":
            return []
        if kind in _SOURCE_PROPERTIES:
            return [()]
        if kind not in _ATOM_RELATIONS:
            raise _error(node, fact, f"unmapped atom kind {kind!r}")
        if kind == "account_state":
            if key != "account_state:reliquary_claimed" or value not in ("true", "false"):
                raise _error(node, fact, f"unmapped account state {key!r} = {value!r}")
            key = f"{key}:{value}"
            self.node(key, "account_state")
            if value == "false":
                self.add(key, (), fact)
        if kind == "world_state" and key not in {row["stable_key"] for row in self.rows("world_states")}:
            raise _error(node, fact, f"unmapped world state {key!r}")
        if kind == "planning_slot_item" and self.slots.get((node, slot)) == "rune":
            slot = "rune slot"
        if quantity is not None and (kind != "encounter_won" or quantity < 1 or int(quantity) != quantity):
            raise _error(node, fact, f"invalid defeat quantity {quantity!r}")
        need = Need(_ATOM_RELATIONS[kind], key, quantity=quantity, slot=slot, advisory=kind == "encounter_won")
        if kind == "encounter_won":
            if key not in self.characters:
                raise _error(node, fact, f"need resolves to no character: {key}")
            count = quantity or 1
            return [
                canonical_way(
                    (
                        need,
                        *(
                            replace(requirement, quantity=(requirement.quantity or 1) * count)
                            if count > 1
                            and (requirement.quantity is not None or requirement.need_stable_key in self.characters)
                            else requirement
                            for requirement in release
                        ),
                    )
                )
                for release in self.kill_needs(str(key))
            ]
        return [(need,)]

    def conditions(self, node: str, atoms: list[dict[str, Any]], fact: str, provenance: bool = False) -> list[Way]:
        gates: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for atom in atoms:
            kind = atom["predicate"] if provenance else atom["atom_kind"]
            if kind not in {*_ATOM_RELATIONS, *_SOURCE_PROPERTIES, "never"}:
                raise _error(node, fact, f"unmapped atom kind {kind!r}")
            if provenance and atom.get("phase", "availability") != "availability":
                continue
            gate = atom["gate_key"] if provenance else atom.get("gate", "condition")
            if provenance and gate.startswith("gate:"):
                gate = json.loads(gate.removeprefix("gate:"))[-1]
            gates[gate][atom["group_index"]].append(atom)
        result: list[Way] = [()]
        for gate, groups in sorted(gates.items()):
            if gate in self.barriers:
                result = self.product(node, result, [(Need("barrier", gate),)], gate)
                continue
            options: list[Way] = []
            for _, group in sorted(groups.items()):
                branch: list[Way] = [()]
                for atom in group:
                    branch = self.product(
                        node,
                        branch,
                        self.atom(
                            node,
                            atom["predicate"] if provenance else atom["atom_kind"],
                            atom.get("reference_stable_key") if provenance else atom["atom_stable_key"],
                            atom.get("reference_slot") if provenance else atom.get("atom_slot"),
                            f"{fact}, gate {gate}",
                            atom.get("value"),
                            (
                                atom.get("minimum")
                                if provenance and atom["predicate"] == "encounter_won"
                                else atom.get("atom_quantity")
                            ),
                        ),
                        gate,
                    )
                options.extend(branch)
            result = self.product(node, result, options, gate)
        return result

    def subject_gates(self, kind: str, key: str, item: str | None = None) -> list[Way]:
        atoms = [
            row
            for row in self.gates.get((kind, key, item), ())
            if _GATE_TREATMENTS[row["gate"].split(":", 1)[0]] != "vulnerability"
        ]
        return self.conditions(key, atoms, f"gate_conditions {kind} {key}")

    def kill_needs(self, character: str, trail: frozenset[str] = frozenset()) -> list[Way]:
        if character in self.kill_cache:
            return self.kill_cache[character]
        row = self.characters[character]
        if not row["can_be_damaged"] or character in trail:
            return []
        if not row["invulnerable"]:
            return [()]
        ways: list[Way] = []
        for (mechanism, source), atoms in sorted(self.releases.get(character, {}).items()):
            fact = f"character_damage_releases {mechanism} {source}"
            if not all(atom["can_release"] and atom["controller_enabled"] for atom in atoms):
                continue
            branch: list[Way] = [()]
            if mechanism == "trade_turn_in":
                variants = [atom["condition_stable_key"] for atom in atoms if atom["condition_kind"] == "quest_variant"]
                if len(variants) != 1 or not self.required.get(variants[0]):
                    raise _error(character, fact, "missing required items for release variant")
                branch = [tuple(replace(need, relation="release") for need in self.required[variants[0]])]
            elif mechanism in {"health_phase_timer", "spawn_health_phase_timer", "combat_empty_wards"}:
                branch = [(Need("condition", condition_key=f"release:{mechanism}:{source}"),)]
            elif mechanism == "npc_protector_weather":
                states = {atom["condition_stable_key"] for atom in atoms if atom["condition_kind"] == "state"}
                if states != {"raining"}:
                    raise _error(character, fact, f"unmapped weather states {sorted(states)}")
                spawns = {atom["condition_stable_key"] for atom in atoms if atom["condition_kind"] == "spawn_point"}
                zones = {
                    placement["zone_stable_key"]
                    for placement in self.placements[character]
                    if placement["zone_stable_key"] and (not spawns or placement["spawn_point_stable_key"] in spawns)
                }
                if len(zones) != 1:
                    raise _error(character, fact, f"weather release needs one bound scene, found {sorted(zones)}")
                branch = []
                for zone in sorted(zones):
                    key = f"world_state:weather:raining:{zone}"
                    for way in self.atom(character, "world_state", key, None, fact):
                        branch.append(tuple(replace(need, relation="release") for need in way))
            elif mechanism in {"shivering_phantom_wards", "combat_ward_cycle", "reliquary_wards"}:
                for atom in atoms:
                    kind, key = atom["condition_kind"], atom["condition_stable_key"]
                    if kind in {"character", "character_dead"}:
                        copies = {key}
                    elif kind == "spawn_point_cleared":
                        copies = self.occupants.get(key, set())
                        if not copies:
                            raise _error(character, fact, f"release spawn has no copies: {key}")
                    elif kind in {"controller", "state"}:
                        continue
                    else:
                        raise _error(character, fact, f"unmapped release condition {kind!r}")
                    options = []
                    for copy in sorted(copies):
                        if copy not in self.characters:
                            raise _error(character, fact, f"release resolves to no copy: {copy}")
                        for release in self.kill_needs(copy, trail | {character}):
                            options.append(canonical_way((Need("release", copy), *release)))
                    branch = self.product(character, branch, options, fact)
            else:
                raise _error(character, fact, "release mechanism has no feasible mapping")
            ways.extend(branch)
        if not trail:
            self.kill_cache[character] = ways
        return ways

    def build_nodes(self) -> None:
        for table, kind in (("zones", "zone"), ("quests", "quest"), ("items", "item"), ("characters", "character")):
            for row in self.rows(table):
                self.node(row["stable_key"], kind)
        for row in self.rows("world_states"):
            self.node(row["stable_key"], "world_state")
        for row in self.rows("weather_spell_effects"):
            self.node(row["spell_stable_key"], "spell")
        # code-fact: progression.playable_classes
        facts = [
            row["value"]
            for row in self.rows("code_facts")
            if row["fact_id"] == "progression.playable_classes" and row["key"] == "strings"
        ]
        if len(facts) != 1 or not facts[0]:
            raise _error("class", "progression.playable_classes", "expected the classes a new character can be")
        known = {row["class_name"] for row in self.rows("classes")}
        for name in facts[0].split(","):
            if name not in known:
                raise _error("class", "progression.playable_classes", f"playable class without a class row: {name}")
            key = "class:" + name.lower()
            self.node(key, "class")
            self.add(key, (), "classes")
        for key in self.barriers:
            self.node(key, "barrier")
        for key, atoms in self.barriers.items():
            groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for atom in atoms:
                groups[atom["group_index"]].append(atom)
            for group in groups.values():
                needs: list[Way] = [()]
                for atom in group:
                    needs = self.product(
                        key,
                        needs,
                        self.atom(key, atom["atom_kind"], atom["atom_stable_key"], atom["atom_slot"], key),
                        key,
                    )
                for way in needs:
                    self.add(key, way, key)

    def build_zones(self) -> None:
        stored = {row["zone_line_stable_key"] for row in self.rows("zone_line_destination_contexts")}
        capable = {row["stable_key"] for row in self.rows("zone_lines_with_zoning_capability")}
        for key, line in sorted(self.lines.items()):
            source = self.scenes.get(line["scene"])
            destination = line["destination_zone_stable_key"]
            if key in stored or not destination:
                continue
            gates = self.gates.get(("zone_line", key, None), [])
            activated = any(row["gate"].startswith("activation") for row in gates)
            if (key not in capable or not line["object_is_active"]) and not activated:
                continue
            if source is None:
                raise _error(destination, key, f"unmapped source scene {line['scene']!r}")
            for way in self.subject_gates("zone_line", key):
                self.add(destination, [Need("zone line", source), *way], key)
        for row in self.rows("teleports"):
            zone = self.scenes.get(row["scene"])
            if zone is None:
                raise _error(str(row["scene"]), row["stable_key"], "unmapped teleport destination scene")
            self.add(zone, [Need("teleport", row["teleport_item_stable_key"])], row["stable_key"])
        # code-fact: progression.start_selection
        if not any(
            row["fact_id"] == "progression.start_selection" and row["key"] == "ok" and row["value"] == "true"
            for row in self.rows("code_facts")
        ):
            raise _error("start", "progression.start_selection", "missing verified new-character start selection")
        # code-fact: progression.new_character_scene
        # code-fact: progression.alternate_start_scene
        for fact, mechanism in START_SCENE_FACTS.items():
            facts = [row for row in self.rows("code_facts") if row["fact_id"] == fact and row["key"] == "string"]
            if len(facts) != 1 or facts[0]["value"] not in self.scenes:
                raise _error(mechanism, fact, "expected one start scene matching a clean zone")
            self.node(mechanism, "mechanism")
            self.add(mechanism, (), fact)
            self.add(self.scenes[facts[0]["value"]], [Need("from", mechanism)], fact)

    def arena_releases(self) -> dict[tuple[str, str], list[Way]]:
        """Return, per scene and character, the ways that Vitheo's arena releases it.

        A round's coin starts the round and spawns its fighters. The round's award
        chest follows once every fighter of the round is dead.
        """
        # code-fact: guide.gates.vitheo_reveal
        rounds = {row["stable_key"]: row for row in self.rows("arena_rounds")}
        fighters: dict[str, Counter[str]] = defaultdict(Counter)
        for row in self.rows("arena_round_enemies"):
            key = row["arena_round_stable_key"]
            if key not in rounds:
                raise _error(row["enemy_character_stable_key"], f"arena_round_enemies {key}", "enemy of no arena round")
            fighters[key][row["enemy_character_stable_key"]] += 1
        releases: dict[tuple[str, str], list[Way]] = defaultdict(list)
        arenas: dict[tuple[str, str], set[str]] = defaultdict(set)
        for key, row in sorted(rounds.items()):
            fact = f"arena_rounds {key}"
            chest = row["award_chest_character_stable_key"]
            if not row["scene"] or not row["arena_object_name"]:
                raise _error(chest, fact, "arena round has no scene or arena identity")
            if not fighters[key]:
                raise _error(chest, fact, "arena round has no fighters")
            coin: Way = (Need("summoned with", row["coin_item_stable_key"]),)
            ways: list[Way] = [coin]
            for fighter, count in sorted(fighters[key].items()):
                releases[row["scene"], fighter].append(coin)
                arenas[row["scene"], fighter].add(row["arena_object_name"])
                defeat = self.atom(
                    chest, "encounter_won", fighter, None, fact, quantity=float(count) if count > 1 else None
                )
                ways = self.product(chest, ways, defeat, fact)
            releases[row["scene"], chest].extend(ways)
            arenas[row["scene"], chest].add(row["arena_object_name"])
        for (scene, character), names in arenas.items():
            if len(names) > 1:
                raise _error(
                    character, f"arena_rounds {scene}", f"placement is ambiguous between arenas {sorted(names)}"
                )
        return releases

    def build_characters(self) -> None:
        stops = self.index("spawn_point_stop_quests", "spawn_point_stable_key")
        encounter_members = self.index("encounter_placements", "member_spawn_stable_key")
        encounter_conditions = self.index("encounter_conditions", "encounter_key")
        arena = self.arena_releases()
        for character, placements in sorted(self.placements.items()):
            for placement in placements:
                spawn = placement["spawn_point_stable_key"]
                fact = f"character_spawns {character} {spawn}"
                zone = placement["zone_stable_key"]
                if not zone:
                    continue
                base = []
                for column, relation, slot in (
                    ("spawn_upon_quest_complete_stable_key", "quest done", None),
                    ("furniture_item_stable_key", "room furnished", placement["furniture_slot"]),
                    ("trigger_item_stable_key", "summoned with", None),
                ):
                    if placement[column]:
                        base.append(Need(relation, placement[column], slot=slot))
                base.extend(Need("quest not done", row["quest_stable_key"]) for row in stops.get(spawn, ()))
                for member in encounter_members.get(spawn, ()):
                    for state in encounter_conditions[member["encounter_key"]]:
                        kind = (
                            "account_state"
                            if state["state_scope"] == "account"
                            else ("quest_done" if state["required_value"] == "true" else "quest_not_done")
                        )
                        for needs in self.atom(
                            character,
                            kind,
                            state["state_key"],
                            None,
                            fact,
                            state["required_value"] if kind == "account_state" else None,
                        ):
                            base.extend(needs)
                releases: list[Way] = [()]
                if placement["source_script"] == "VithArena":
                    releases = arena.get((placement["scene"], character), [])
                    if not releases:
                        raise _error(character, fact, "arena placement belongs to no round")
                ways = self.product(character, [tuple(base)], releases, fact)
                ways = self.product(character, ways, self.subject_gates("character", character), fact)
                if spawn:
                    ways = self.product(character, ways, self.subject_gates("spawn_point", spawn), fact)
                entries = self.entries.get(("character", character), set()) | self.entries.get(
                    ("spawn_point", spawn), set()
                )
                if entries:
                    locations = []
                    for entry in sorted(entries):
                        if entry not in self.lines or self.lines[entry]["scene"] not in self.scenes:
                            raise _error(character, fact, f"unmapped entry line {entry}")
                        entry_zone = self.scenes[self.lines[entry]["scene"]]
                        for gate in self.subject_gates("zone_line", entry):
                            locations.append(canonical_way((Need("entered from", entry_zone), *gate)))
                else:
                    locations = [(Need("in zone", zone),)]
                for way in self.product(character, ways, locations, fact):
                    self.add(character, way, fact)

    def location_conditions(self, node: str, location: dict[str, Any], fact: str) -> list[Way]:
        atoms = [asdict(condition_from_dict(atom)) for atom in json.loads(location["conditions"])]
        return self.conditions(node, atoms, fact, provenance=True)

    def mechanism(self, key: str, locations: list[dict[str, Any]], fact: str) -> None:
        self.node(key, "mechanism")
        if not locations:
            self.add(key, (), fact)
            return
        for location in locations:
            base = [Need("in zone", location["zone_stable_key"])] if location["zone_stable_key"] else []
            for way in self.location_conditions(key, location, fact):
                self.add(key, [*base, *way], fact)

    def build_items(self) -> None:
        materials = self.index("item_uses", "target_stable_key")
        for acquisition in self.rows("item_acquisitions"):
            node, fact, kind = acquisition["item_stable_key"], acquisition["acquisition_key"], acquisition["kind"]
            if kind not in {*ACQUISITION_RELATIONS, "internal_equipment", "auction_house"}:
                raise _error(node, fact, f"unmapped acquisition kind {kind!r}")
            if acquisition["player_access_state"] not in {"verified_player", "unconfirmed_player"}:
                continue
            # Simulated players list random stock, so no player can plan a step on it.
            if kind == "auction_house":
                continue
            if kind == "internal_equipment":
                raise _error(node, fact, "internal equipment cannot be a player acquisition")
            relation = ACQUISITION_RELATIONS[kind]
            source = acquisition["source_stable_key"]
            conditions = self.conditions(node, self.acquisition_conditions.get(fact, []), fact, provenance=True)
            bases: list[Way] = []
            locations = self.locations.get(fact, [])
            if kind in {"character_drop", "vendor", "dialog"}:
                source = acquisition["source_copy_stable_key"]
                if source not in self.characters:
                    raise _error(node, fact, f"need resolves to no source copy: {source}")
                releases = self.kill_needs(source) if kind == "character_drop" else [()]
                bases = [canonical_way((Need(relation, source), *release)) for release in releases]
            elif kind in {"mining", "fishing", "fishing_bonus", "item_bag"}:
                for location in locations:
                    zone = location["zone_stable_key"]
                    if zone:
                        for way in self.location_conditions(node, location, fact):
                            bases.append(canonical_way((Need(relation, zone), *way)))
            elif kind == "crafting":
                needs = [Need(relation, source)]
                for use in materials.get(source, ()):
                    if use["kind"] == "crafting_material":
                        needs.append(
                            Need(
                                "material",
                                use["item_stable_key"],
                                quantity=use["quantity_min"],
                                slot=str(use["material_slot"]),
                            )
                        )
                bases = [tuple(needs)]
            elif kind in {"common_world_item", "special_world_drop", "ui_grant"}:
                source = source or "mechanic:" + kind
                self.mechanism(source, locations, fact)
                bases = [(Need(relation, source),)]
            else:
                bases = [(Need(relation, source),)]
            # Locations already belong to character copies. Only source-local predicates join here.
            for base in bases:
                for condition in conditions:
                    way = canonical_way((*base, *condition))
                    if acquisition["player_access_state"] == "unconfirmed_player":
                        way = tuple(replace(need, unconfirmed=True) for need in way)
                    self.add(node, way, fact)

    def build_quests(self) -> None:
        routes = self.rows("quest_routes")
        started = {row["quest_stable_key"] for row in routes if row["phase"] == "start"}
        for quest in started:
            self.node("quest_start:" + quest, "quest_start")
        for route in routes:
            quest, phase, method = route["quest_stable_key"], route["phase"], route["method"]
            node = "quest_start:" + quest if phase == "start" else quest
            fact = f"quest_routes {route['route_key']}"
            relation = ROUTE_RELATIONS.get(phase, {}).get(method)
            if relation is None:
                raise _error(node, fact, f"unmapped route method {phase} {method!r}")
            source, kind = route["source_stable_key"], route["source_kind"]
            if kind not in {"character", "item", "quest", "zone", "scripted"}:
                raise _error(node, fact, f"unmapped source kind {kind!r}")
            if kind == "scripted":
                base = [Need("event", condition_key="event:" + (source or route["route_key"]))]
            else:
                if source not in self.kinds or self.kinds[source] != kind:
                    raise _error(node, fact, f"need resolves to no {kind} node: {source}")
                base = [Need(relation, source, keywords=route["keywords"])]
            if phase == "completion" and quest in started:
                base.append(Need("started", "quest_start:" + quest))
            if method == "item_turnin":
                base.extend(self.required[route["variant_resource_name"]])
            variants = [tuple(base)]
            if method == "partial_turnin":
                variants = [
                    (*base, replace(need, quantity=1)) for need in self.required[route["variant_resource_name"]]
                ]
            if method == "death":
                variants = self.product(node, variants, self.kill_needs(source), fact)
            atoms = [row | {"gate": row["gate_key"]} for row in self.route_conditions.get(route["route_key"], [])]
            for way in self.product(node, variants, self.conditions(node, atoms, fact), fact):
                self.add(node, way, fact)
        quest_of_variant = {row["resource_name"]: row["quest_stable_key"] for row in self.rows("quest_variants")}
        executable = {row["variant_resource_name"] for row in routes if row["grants_resource_rewards"]}
        for row in self.rows("quest_complete_other_quests"):
            other = row["completed_quest_stable_key"]
            variant = row["quest_variant_resource_name"]
            if other in started and variant in executable:
                self.add(
                    other,
                    [Need("after", quest_of_variant[variant]), Need("quest active", "quest_start:" + other)],
                    f"quest_complete_other_quests {variant}",
                )

    def item_action(self, item: dict[str, Any], relation: str, required_level: int | None = None) -> list[Way]:
        # code-fact: progression.item_action_guards
        if not any(
            row["fact_id"] == "progression.item_action_guards" and row["key"] == "ok" and row["value"] == "true"
            for row in self.rows("code_facts")
        ):
            raise _error(item["stable_key"], "progression.item_action_guards", "missing verified item action rules")
        if relation not in {"casts", "teaches", "equipped"}:
            raise _error(item["stable_key"], "item action", f"unmapped item action {relation!r}")
        if required_level is not None and (type(required_level) is not int or required_level < 0):
            raise _error(item["stable_key"], "spells.required_level", "invalid spell learning level")
        playable = {key for key, kind in self.kinds.items() if kind == "class"}
        allowed = {
            "class:" + row["class_name"].lower()
            for row in self.rows("item_classes")
            if row["item_stable_key"] == item["stable_key"]
        }
        known = {"class:" + row["class_name"].lower() for row in self.rows("classes")}
        if not allowed <= known:
            raise _error(item["stable_key"], "item_classes", f"unknown allowed classes {sorted(allowed - known)}")
        if relation == "casts":
            # General-slot click effects bypass class membership. Other click
            # effects require membership even when the class list is empty.
            if item["required_slot"] == "General":
                allowed = playable
        elif not allowed:
            allowed = playable
        allowed &= playable
        base = [Need(relation, item["stable_key"], required_level=required_level)]
        if relation == "casts" and item["must_be_equipped_to_click"]:
            base.append(Need("equipped", item["stable_key"]))
        if allowed == playable:
            return [canonical_way(base)]
        return [canonical_way((*base, Need("class", key))) for key in sorted(allowed)]

    def build_weather(self) -> None:
        states = {row["stable_key"]: row for row in self.rows("world_states")}
        for row in self.rows("world_state_producers"):
            state = states[row["state_stable_key"]]
            needs = [Need("in zone", state["zone_stable_key"])]
            if row["mechanism"] == "spell":
                needs.append(Need("cast", row["spell_stable_key"]))
            elif row["mechanism"] == "natural_weather":
                needs.append(Need("natural weather", condition_key="weather:natural_rain"))
            else:
                raise _error(state["stable_key"], "world_state_producers", "unmapped weather producer")
            self.add(state["stable_key"], needs, "world_state_producers")
        spells = {
            row["stable_key"]: row
            for row in self.rows("spells")
            if row["stable_key"] in {effect["spell_stable_key"] for effect in self.rows("weather_spell_effects")}
        }
        for item in self.rows("items"):
            for column, relation in (
                ("item_effect_on_click_stable_key", "casts"),
                ("teach_spell_stable_key", "teaches"),
            ):
                if item[column] in spells:
                    spell = spells[item[column]]
                    level = spell["required_level"] if relation == "teaches" else None
                    if relation == "teaches" and level is None:
                        raise _error(item[column], "spells.required_level", "missing spell learning level")
                    for way in self.item_action(item, relation, level):
                        self.add(item[column], way, f"items.{column}")

    def build_states(self) -> None:
        members = self.index("encounter_placements", "encounter_key")
        guards = self.index("encounter_event_conditions", "encounter_key")
        for effect in self.rows("encounter_completions"):
            key = effect["state_key"]
            if effect["state_scope"] == "account":
                key = f"{key}:{effect['result_value']}"
                self.node(key, "account_state")
            fact = f"encounter_completions {effect['encounter_key']} {effect['event_kind']}"
            if effect["result_value"] != "true":
                raise _error(key, fact, f"unmapped state result {effect['result_value']!r}")
            ways: list[Way] = [()]
            if effect["event_kind"] == "host_death":
                ways = []
                for member in members[effect["encounter_key"]]:
                    if member["role"] == "root":
                        for copy in sorted(self.occupants[member["root_spawn_stable_key"]]):
                            for release in self.kill_needs(copy):
                                ways.append(canonical_way((Need("defeated", copy, advisory=True), *release)))
            elif effect["event_kind"] not in {"scene_awake_quest_completed", "scene_awake_account_claimed"}:
                raise _error(key, fact, f"unmapped encounter event {effect['event_kind']!r}")
            for guard in guards[effect["encounter_key"]]:
                if guard["event_kind"] != effect["event_kind"]:
                    continue
                kind = (
                    "account_state"
                    if guard["state_scope"] == "account"
                    else ("quest_done" if guard["required_value"] == "true" else "quest_not_done")
                )
                ways = self.product(
                    key,
                    ways,
                    self.atom(
                        key,
                        kind,
                        guard["state_key"],
                        None,
                        fact,
                        guard["required_value"] if kind == "account_state" else None,
                    ),
                    fact,
                )
            for way in ways:
                self.add(key, way, fact)

    def mark_milestones(self) -> None:
        gated = {
            node
            for node, ways in self.ways.items()
            if ways and all(any(need.relation in _GATE_RELATIONS for need in way) for way in ways.values())
        }
        gate_items = {
            need.need_stable_key
            for ways in self.ways.values()
            for way in ways.values()
            for need in way
            if need.relation in _GATE_RELATIONS and self.kinds.get(need.need_stable_key or "") == "item"
        }
        for node, kind in self.kinds.items():
            if kind in {"quest", "barrier", "world_state"} or (kind in {"zone", "character"} and node in gated):
                self.milestones.add(node)
            elif kind == "item":
                ways = self.ways.get(node, {})
                if node in gate_items or (
                    ways
                    and all(
                        any(need.relation in {"reward", "mold"} for need in way)
                        or any(
                            need.relation in {"drops", "sells", "gives"} and need.need_stable_key in gated
                            for need in way
                        )
                        for way in ways.values()
                    )
                ):
                    self.milestones.add(node)

    def need_tier(self, need: Need) -> int | None:
        if need.need_stable_key is None or need.relation == "quest not done":
            return 0
        return self.tiers.get(need.need_stable_key)

    def way_tier(self, node: str, way: Way) -> int | None:
        tiers = [self.need_tier(need) for need in way]
        if any(tier is None for tier in tiers):
            return None
        return max((tier for tier in tiers if tier is not None), default=0) + int(node in self.milestones)

    def way_depth(self, way: Way) -> int | None:
        depths = [
            0
            if need.need_stable_key is None or need.relation == "quest not done"
            else self.depths.get(need.need_stable_key)
            for need in way
        ]
        if any(depth is None for depth in depths):
            return None
        return 1 + max((depth for depth in depths if depth is not None), default=-1)

    def order(self) -> None:
        changed = True
        while changed:
            changed = False
            for node, ways in sorted(self.ways.items()):
                for way in ways.values():
                    tier = self.way_tier(node, way)
                    if tier is not None and (node not in self.tiers or tier < self.tiers[node]):
                        self.tiers[node] = tier
                        changed = True
        # Stabilize tiers before minimizing depth, so a falling tier cannot leave a stale depth.
        changed = True
        while changed:
            changed = False
            for node, ways in sorted(self.ways.items()):
                if node not in self.tiers:
                    continue
                for key, way in sorted(ways.items()):
                    if self.way_tier(node, way) != self.tiers[node]:
                        continue
                    depth = self.way_depth(way)
                    if depth is None:
                        continue
                    if node not in self.depths or (depth, key) < (self.depths[node], self.first[node]):
                        self.depths[node], self.first[node] = depth, key
                        changed = True
        self.check_tiers()
        self.check_first_ways()
        self.rank_ways()

    def rank_ways(self) -> None:
        """Give each usable way the tier and depth by which first ways are chosen."""
        for node, ways in self.ways.items():
            for key, way in ways.items():
                tier = self.way_tier(node, way)
                depth = self.way_depth(way)
                if tier is not None and depth is not None:
                    self.ranks[node, key] = (tier, depth)
        for node, first in self.first.items():
            lowest = min((self.ranks[node, key], key) for key in self.ways[node] if (node, key) in self.ranks)
            if lowest != ((self.tiers[node], self.depths[node]), first):
                raise _error(node, "way rank", f"first way does not have the lowest rank {lowest}", first)

    def check_tiers(self) -> None:
        for node, tier in self.tiers.items():
            key = self.first[node]
            for need in self.ways[node][key]:
                value = self.need_tier(need)
                if value is None or value > tier or (node in self.milestones and value >= tier):
                    raise _error(node, str(need), "tier invariant violated", key)

    def check_first_ways(self) -> None:
        complete: set[str] = set()
        active: set[str] = set()

        def visit(node: str) -> None:
            if node in complete:
                return
            if node in active:
                raise _error(node, "first-way explanation", "first way revisits a node", self.first[node])
            active.add(node)
            key = self.first[node]
            for need in self.ways[node][key]:
                target = need.need_stable_key
                if target is None or need.relation == "quest not done":
                    continue
                if target not in self.first:
                    raise _error(node, str(need), "first way has no start-rooted explanation", key)
                if self.depths[target] >= self.depths[node]:
                    raise _error(node, str(need), "first-way depth does not decrease", key)
                visit(target)
            active.remove(node)
            complete.add(node)

        for node in sorted(self.tiers):
            visit(node)

    def build(self) -> None:
        self.build_nodes()
        self.build_zones()
        self.build_weather()
        self.build_characters()
        self.build_items()
        self.build_quests()
        self.build_states()
        self.mark_milestones()
        self.order()

    def write(self) -> None:
        builds = self.rows("code_facts_meta")
        if len(builds) != 1 or not builds[0]["game_build_id"]:
            raise _error("metadata", "code_facts_meta", "expected one nonempty build id")
        conn = self.connection
        for table in (
            "progression_way_facts",
            "progression_needs",
            "progression_ways",
            "progression_nodes",
            "progression_meta",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.executemany(
            "INSERT INTO progression_nodes VALUES (?,?,?,?,?)",
            [
                (node, kind, int(node in self.milestones), self.tiers.get(node), self.first.get(node))
                for node, kind in sorted(self.kinds.items())
            ],
        )
        conn.executemany(
            "INSERT INTO progression_ways VALUES (?,?,?,?)",
            [
                (node, key, *self.ranks.get((node, key), (None, None)))
                for node, ways in sorted(self.ways.items())
                for key in sorted(ways)
            ],
        )
        conn.executemany(
            "INSERT INTO progression_way_facts VALUES (?,?,?)",
            [
                (node, key, fact)
                for node, ways in sorted(self.ways.items())
                for key in sorted(ways)
                for fact in sorted(self.facts[node, key])
            ],
        )
        conn.executemany(
            "INSERT INTO progression_needs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    node,
                    key,
                    index,
                    need.relation,
                    need.need_stable_key,
                    need.quantity,
                    need.slot,
                    need.keywords,
                    need.condition_key,
                    int(need.advisory),
                    int(need.unconfirmed),
                    need.required_level,
                )
                for node, ways in sorted(self.ways.items())
                for key, way in sorted(ways.items())
                for index, need in enumerate(way)
            ],
        )
        conn.execute(
            "INSERT INTO progression_meta VALUES (?,?)", (PROGRESSION_SCHEMA_VERSION, builds[0]["game_build_id"])
        )


def process_progression(connection: sqlite3.Connection) -> None:
    """Persist canonical alternatives, milestones, and earliest playthrough tiers."""
    started = perf_counter()
    builder = ProgressionBuilder(connection)
    builder.build()
    builder.write()
    connection.commit()
    for label, nodes in (
        ("without a way", set(builder.kinds) - builder.ways.keys()),
        ("without a tier", set(builder.kinds) - builder.tiers.keys()),
    ):
        logger.info(
            "Progression nodes {}: {}", label, dict(sorted(Counter(builder.kinds[node] for node in nodes).items()))
        )
    logger.info(
        "Progression graph: {} nodes, {} ways, {:.3f}s",
        len(builder.kinds),
        sum(map(len, builder.ways.values())),
        perf_counter() - started,
    )
