"""Read and validate the common encounter boundary without deriving native identity."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .graph import EntityGraph

_FIELDS = {
    "encounter_placements": (
        "encounter_key",
        "root_spawn_stable_key",
        "member_spawn_stable_key",
        "role",
        "context_kind",
        "post_completion_role",
    ),
    "encounter_conditions": ("encounter_key", "state_scope", "state_key", "required_value"),
    "encounter_completions": ("encounter_key", "event_kind", "state_scope", "state_key", "result_value"),
    "encounter_event_conditions": ("encounter_key", "event_kind", "state_scope", "state_key", "required_value"),
}
_ACCOUNT = "account_state:reliquary_claimed"
_LOADED_FACTS = (
    "guide.gates.reliquary_claim_loaded",
    "guide.state.reliquary_load_before_play",
    "guide.state.reliquary_load_before_play_alternate",
)


def validate_loaded_state_contract(conn: sqlite3.Connection) -> None:
    """Require verified account loading and both pre-world-entry call sites."""
    # code-fact: guide.gates.reliquary_claim_loaded
    # code-fact: guide.state.reliquary_load_before_play
    # code-fact: guide.state.reliquary_load_before_play_alternate
    for fact in _LOADED_FACTS:
        try:
            rows = conn.execute(
                "SELECT value, value_type FROM code_facts WHERE fact_id = ? AND key = 'ok'", (fact,)
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("Encounter account binding requires code_facts") from exc
        if len(rows) != 1 or tuple(rows[0]) != ("true", "bool"):
            raise ValueError(f"Encounter account binding requires one verified bool true code fact: {fact}")


def read_encounter_contexts(conn: sqlite3.Connection) -> dict[str, list[dict[str, object]]]:
    """Preserve canonical rows and reject incomplete or unsupported state projections."""
    result: dict[str, list[dict[str, object]]] = {}
    for table, fields in _FIELDS.items():
        try:
            rows = conn.execute(f"SELECT {', '.join(fields)} FROM {table} ORDER BY {', '.join(fields)}").fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"Missing or incompatible encounter table: {table}") from exc
        result[table] = [dict(zip(fields, row, strict=True)) for row in rows]
        identities: set[tuple[object, ...]] = set()
        for row in result[table]:
            if any(not isinstance(value, str) or not value.strip() for value in row.values()):
                raise ValueError(f"Encounter row requires nonempty canonical fields: {table}")
            identity = tuple(row[field] for field in fields if field not in {"required_value", "result_value"})
            if identity in identities:
                raise ValueError(f"Duplicate encounter row: {table}")
            identities.add(identity)

    placements = result["encounter_placements"]
    encounters = {row["encounter_key"] for row in placements}
    for table in tuple(_FIELDS)[1:]:
        for row in result[table]:
            if row["encounter_key"] not in encounters:
                raise ValueError(f"Encounter state has no placement: {row['encounter_key']}")
    if not encounters:
        return result
    try:
        spawns = {row[0] for row in conn.execute("SELECT spawn_point_stable_key FROM character_spawns")}
        quests = {row[0] for row in conn.execute("SELECT stable_key FROM quests")}
    except sqlite3.DatabaseError as exc:
        raise ValueError("Encounter references require clean quests and character_spawns") from exc

    for encounter in sorted(encounters, key=str):
        members = [row for row in placements if row["encounter_key"] == encounter]
        roots = {row["root_spawn_stable_key"] for row in members}
        root_rows = [row for row in members if row["role"] == "root"]
        if len(roots) != 1 or len(root_rows) != 1:
            raise ValueError(f"Encounter requires exactly one root: {encounter}")
        root = next(iter(roots))
        member_keys: set[object] = set()
        for row in members:
            member = row["member_spawn_stable_key"]
            if member not in spawns or root not in spawns:
                raise ValueError(f"Encounter member has no actual placement: {member}")
            if member in member_keys or row["role"] != ("root" if member == root else "support"):
                raise ValueError(f"Invalid encounter membership: {member}")
            member_keys.add(member)
            if row["context_kind"] != "account_claim" or row["post_completion_role"] != "player_home":
                raise ValueError(f"Unsupported encounter purpose metadata: {encounter}")

        states: dict[str, set[tuple[object, ...]]] = {}
        for table in tuple(_FIELDS)[1:]:
            rows = [row for row in result[table] if row["encounter_key"] == encounter]
            value_field = "result_value" if table == "encounter_completions" else "required_value"
            states[table] = set()
            for row in rows:
                scope, key, value = row["state_scope"], row["state_key"], row[value_field]
                if value not in {"true", "false"}:
                    raise ValueError(f"Invalid encounter boolean: {value}")
                if not ((scope == "account" and key == _ACCOUNT) or (scope == "character" and key in quests)):
                    raise ValueError(f"Unsupported encounter state reference: {scope}:{key}")
                state: tuple[object, ...] = (scope, key, value)
                if table != "encounter_conditions":
                    state = (row["event_kind"], *state)
                if state in states[table]:
                    raise ValueError(f"Duplicate encounter state: {table}")
                states[table].add(state)
        character_conditions = [state for state in states["encounter_conditions"] if state[0] == "character"]
        if len(character_conditions) != 1:
            raise ValueError(f"Encounter requires one character quest condition: {encounter}")
        quest = character_conditions[0][1]
        if states["encounter_conditions"] != {("account", _ACCOUNT, "false"), ("character", quest, "false")}:
            raise ValueError(f"Unsupported encounter availability conditions: {encounter}")
        expected_effects = {
            ("host_death", "account", _ACCOUNT, "true"),
            ("host_death", "character", quest, "true"),
            ("scene_awake_quest_completed", "account", _ACCOUNT, "true"),
            ("scene_awake_account_claimed", "character", quest, "true"),
        }
        expected_guards = {
            ("scene_awake_quest_completed", "character", quest, "true"),
            ("scene_awake_account_claimed", "account", _ACCOUNT, "true"),
        }
        if states["encounter_completions"] != expected_effects:
            raise ValueError(f"Unsupported or incomplete encounter effects: {encounter}")
        if states["encounter_event_conditions"] != expected_guards:
            raise ValueError(f"Unsupported or incomplete encounter guards: {encounter}")
    validate_loaded_state_contract(conn)
    return result


def read_zone_line_destination_contexts(conn: sqlite3.Connection, graph: EntityGraph) -> dict[str, dict[str, object]]:
    """Read the common destination binding without deriving a second classifier."""
    fields = ("zone_line_stable_key", "kind", "destination_state_key", "landing_state_key", "source_key")
    try:
        rows = conn.execute(
            f"SELECT {', '.join(fields)} FROM zone_line_destination_contexts ORDER BY zone_line_stable_key"
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise ValueError("Missing or incompatible zone_line_destination_contexts") from exc
    result: dict[str, dict[str, object]] = {}
    for values in rows:
        row = dict(zip(fields, values, strict=True))
        key = row["zone_line_stable_key"]
        if not isinstance(key, str) or key in result or not graph.has_node(key):
            raise ValueError(f"Destination context requires one actual guide line: {key}")
        if (
            row["kind"] != "stored_return"
            or row["destination_state_key"] != "character_state:reliquary_return_zone"
            or row["landing_state_key"] != "character_state:reliquary_return_landing"
            or not isinstance(row["source_key"], str)
            or not row["source_key"]
        ):
            raise ValueError(f"Unsupported zone line destination context: {key}")
        result[key] = row
    return result
