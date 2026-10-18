"""Select executable quest routes after canonical item provenance."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

# Source kinds are part of each native operation, not interchangeable labels.
_METHODS = {
    "start": {
        "dialog": "character",
        "quest_chain": "quest",
        "item_read": "item",
        "zone_entry": "zone",
        "partial_turnin": "character",
        "scripted": "scripted",
    },
    "completion": {
        "item_turnin": "character",
        "talk": "character",
        "zone": "zone",
        "read": "item",
        "death": "character",
        "chain": "quest",
        # Scripted completions come from scripted_events, in the event's zone.
        "scripted": "zone",
        "shout": "character",
    },
}
_CONDITIONS = {"quest_done", "quest_not_done", "item_not_owned"}
# A scripted event can also need a carried item, such as Bellwain's flint.
_EVENT_CONDITIONS = _CONDITIONS | {"item_held"}
_DIALOG_GATES = {"not_owned", "dialog_prerequisite", "dialog_assignment"}


def _rows(connection: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    cursor = connection.execute(query)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor]


def process_quest_routes(connection: sqlite3.Connection) -> int:
    """Persist route identity separately from source placement availability."""
    variants = _rows(
        connection,
        """
        SELECT v.*, COALESCE((SELECT SUM(quantity) FROM quest_required_items r
        WHERE r.quest_variant_resource_name = v.resource_name), 0) AS required_count
        FROM quest_variants v ORDER BY resource_name
    """,
    )
    dialogs = _rows(connection, "SELECT * FROM character_dialogs ORDER BY character_stable_key, dialog_index")
    groups = {
        row["member_stable_key"]: row["group_key"]
        for row in _rows(connection, "SELECT * FROM character_deduplications ORDER BY member_stable_key")
    }
    acquisitions = _rows(
        connection,
        """
        SELECT * FROM item_acquisitions WHERE kind IN ('quest_reward', 'dialog') ORDER BY acquisition_key
    """,
    )
    trade_rewards = [fact for fact in acquisitions if fact["kind"] == "quest_reward"]
    dialog_rewards = {
        (fact["source_copy_stable_key"], fact["variant_key"]): fact for fact in acquisitions if fact["kind"] == "dialog"
    }
    dialog_conditions: dict[str, list[dict[str, Any]]] = {}
    for atom in _rows(connection, "SELECT * FROM item_acquisition_conditions ORDER BY owner_key, gate_key"):
        if atom["gate_key"] in _DIALOG_GATES:
            dialog_conditions.setdefault(atom["owner_key"], []).append(atom)
    event_conditions: dict[str, list[dict[str, Any]]] = {}
    for atom in _rows(
        connection, "SELECT * FROM scripted_event_conditions ORDER BY event_key, group_index, atom_index"
    ):
        event_conditions.setdefault(atom["event_key"], []).append(atom)
    turnin_variants: dict[tuple[str, str], set[str]] = {}
    for manager in _rows(connection, "SELECT * FROM character_quest_manager_quests"):
        turnin_variants.setdefault((manager["quest_stable_key"], manager["character_stable_key"]), set()).add(
            manager["quest_variant_resource_name"]
        )
    sources = {
        phase: _rows(
            connection, f"SELECT DISTINCT * FROM {table} ORDER BY quest_stable_key, method, source_stable_key, note"
        )
        for phase, table in (("start", "quest_acquisition_sources"), ("completion", "quest_completion_sources"))
    }
    # Validate even rows that an execution rule later excludes.
    for phase, records in sources.items():
        for record in records:
            quest, method, kind = record["quest_stable_key"], record["method"], record["source_type"]
            if method not in _METHODS[phase]:
                raise ValueError(f"Quest {quest}: unmapped {phase} method {method!r}")
            if kind != _METHODS[phase][method]:
                raise ValueError(f"Quest {quest}: unmapped source kind {kind!r} for {phase} method {method}")
    # Unplaced backup copies cannot execute NPCDialog or TradeWindow operations.
    # The shared view also retains mapping-generated unresolved scripted sources.
    encountered = {
        row["member_stable_key"] for row in _rows(connection, "SELECT member_stable_key FROM character_fact_sources")
    }
    sources = {
        phase: [row for row in records if row["source_type"] != "character" or row["source_stable_key"] in encountered]
        for phase, records in sources.items()
    }
    turnin_quests = {row["quest_stable_key"] for row in sources["completion"] if row["method"] == "item_turnin"}
    routes: dict[str, dict[str, Any]] = {}
    conditions: dict[str, list[tuple[str, int, int, str, str]]] = {}

    def append(
        record: dict[str, Any],
        phase: str,
        *,
        variant: str | None = None,
        dialog: dict[str, Any] | None = None,
        event: str | None = None,
    ) -> None:
        quest, method = record["quest_stable_key"], record["method"]
        source, kind = record["source_stable_key"], record["source_type"]
        index = dialog["dialog_index"] if dialog else None
        identity = json.dumps([quest, phase, method, kind, source, variant, index], separators=(",", ":"))
        key = "quest_route:" + hashlib.sha256(identity.encode()).hexdigest()
        route = {
            "route_key": key,
            "quest_stable_key": quest,
            "phase": phase,
            "method": method,
            "source_kind": kind,
            "source_stable_key": source,
            "source_group_key": groups.get(source) if kind == "character" else None,
            "variant_resource_name": variant,
            "dialog_index": index,
            "keywords": (dialog["keywords"] or None) if dialog else None,
            "note": record["note"] or None,
            # GameData.FinishQuest grants no TradeWindow.CompleteTrade resource effects.
            "grants_resource_rewards": int(phase == "completion" and method == "item_turnin"),
        }
        atoms: list[tuple[str, int, int, str, str]] = []

        def condition(gate: str, predicate: str, reference: str) -> None:
            if predicate not in _CONDITIONS or not reference:
                raise ValueError(f"Quest {quest}: unmapped condition {gate}:{predicate}:{reference}")
            atoms.append((gate, 0, 0, predicate, reference))

        if dialog:
            # NPCDialog.GiveItem checks carried ownership before executing the dialog gift.
            if dialog["give_item_stable_key"]:
                condition("not_owned", "item_not_owned", dialog["give_item_stable_key"])
            # NPCDialog checks required completion and QuestAvailable for assigned quests.
            if dialog["required_quest_stable_key"]:
                condition("dialog_prerequisite", "quest_done", dialog["required_quest_stable_key"])
            assigned = dialog["assign_quest_stable_key"]
            if assigned:
                repeat_flags = {bool(v["repeatable"]) for v in variants if v["quest_stable_key"] == assigned}
                if len(repeat_flags) != 1:
                    raise ValueError(
                        f"Quest {quest}: cannot resolve dialog {source}:{index} assignment condition for {assigned}"
                    )
                if False in repeat_flags:
                    condition("dialog_assignment", "quest_not_done", assigned)
            gift = dialog_rewards.get((source, str(index)))
            if gift:
                if gift["quantity_min"] is None or gift["quantity_min"] != gift["quantity_max"]:
                    raise ValueError(f"Quest {quest}: dialog grant {gift['acquisition_key']} has no exact quantity")
                for atom in dialog_conditions.get(gift["acquisition_key"], []):
                    if atom["predicate"] not in _CONDITIONS:
                        raise ValueError(f"Quest {quest}: unmapped condition {atom['gate_key']}:{atom['predicate']}")
        for atom in event_conditions.get(event, []) if event else []:
            if atom["atom_kind"] not in _EVENT_CONDITIONS:
                raise ValueError(f"Quest {quest}: unmapped event condition {atom['atom_kind']}")
            atoms.append(("event", atom["group_index"], atom["atom_index"], atom["atom_kind"], atom["atom_stable_key"]))
        if key in routes and (routes[key] != route or conditions[key] != sorted(atoms)):
            raise ValueError(f"Quest {quest}: conflicting route {key}")
        routes[key], conditions[key] = route, sorted(atoms)

    for phase, records in sources.items():
        for record in records:
            quest, method, source = record["quest_stable_key"], record["method"], record["source_stable_key"]
            # TradeWindow.CompleteTrade completes other active quests only from a turn-in.
            if method == "chain" and source not in turnin_quests:
                continue
            if method in {"dialog", "talk"}:
                column = "assign_quest_stable_key" if phase == "start" else "complete_quest_stable_key"
                matching = [d for d in dialogs if d["character_stable_key"] == source and d[column] == quest]
                for dialog in matching:
                    append(record, phase, dialog=dialog)
                if matching:
                    continue
            if method == "quest_chain":
                # TradeWindow.CompleteTrade assigns the next quest from the executing resource.
                matching_variants = [
                    v
                    for v in variants
                    if v["quest_stable_key"] == source and v["assign_new_quest_on_complete_stable_key"] == quest
                ]
                for variant in matching_variants:
                    append(record, phase, variant=variant["resource_name"])
                if matching_variants:
                    continue
            if method == "partial_turnin":
                # TradeWindow.CompleteTrade assigns only with partial dialog and a proper subset of units.
                for variant in variants:
                    if (
                        variant["quest_stable_key"] == quest
                        and variant["assign_this_quest_on_partial_complete"]
                        and variant["dialog_on_partial_success"]
                        and variant["required_count"] > 1
                    ):
                        append(record, phase, variant=variant["resource_name"])
                continue
            if method == "item_turnin":
                # QuestAvailable ignores DisableQuest. Canonical rewards identify executed item grants.
                rewards = [
                    f
                    for f in trade_rewards
                    if f["source_stable_key"] == quest and f["source_copy_stable_key"] == source
                ]
                for reward in rewards:
                    if reward["quantity_min"] is None or reward["quantity_min"] != reward["quantity_max"]:
                        raise ValueError(f"Quest {quest}: item grant {reward['acquisition_key']} has no exact quantity")
                matching_resources = turnin_variants.get((quest, source), set())
                if not matching_resources:
                    raise ValueError(f"Quest {quest}: item_turnin source {source} has no resource variant")
                for resource in sorted(matching_resources):
                    append(record, phase, variant=resource)
                continue
            append(record, phase)
    for event in _rows(connection, "SELECT * FROM scripted_events ORDER BY event_key"):
        record = {
            "quest_stable_key": event["quest_stable_key"],
            "method": "scripted",
            "source_type": "zone",
            "source_stable_key": event["zone_stable_key"],
            "note": event["note"],
        }
        append(record, "completion", event=event["event_key"])
    for key in sorted(routes):
        row = routes[key]
        connection.execute(
            f"INSERT INTO quest_routes ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values())
        )
        connection.executemany(
            "INSERT INTO quest_route_conditions VALUES (?, ?, ?, ?, ?, ?)", [(key, *atom) for atom in conditions[key]]
        )
    # Writer.finalize vacuums after late-stage inserts.
    connection.commit()
    return len(routes)
