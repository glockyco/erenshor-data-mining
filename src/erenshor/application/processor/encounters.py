"""Bind encounter membership and state transitions to actual exported placements."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from loguru import logger

from .gates import _scripted_reference

if TYPE_CHECKING:
    from .writer import Writer

_ACCOUNT_STATE = "account_state:reliquary_claimed"
_CLAIM_FACTS = (
    "guide.gates.reliquary_sources",
    "guide.gates.reliquary_wards",
    "guide.gates.reliquary_claim_awake",
    "guide.gates.reliquary_claim_saved",
    "guide.gates.reliquary_claim_loaded",
)


def build_encounter_rows(raw: sqlite3.Connection, conn: sqlite3.Connection) -> dict[str, list[dict[str, object]]]:
    """Preserve the claiming root, its support placements and guarded account effects."""
    result: dict[str, list[dict[str, object]]] = {
        "encounter_placements": [],
        "encounter_conditions": [],
        "encounter_completions": [],
        "encounter_event_conditions": [],
    }
    roots = {
        str(row[0])
        for row in conn.execute(
            "SELECT DISTINCT source_stable_key FROM character_damage_releases "
            "WHERE mechanism = 'reliquary_wards' AND condition_kind = 'controller'"
        )
    }
    sources = raw.execute(
        "SELECT SourceKey FROM ScriptedActivators WHERE RuleId = 'reliquary_account_claim' ORDER BY SourceKey"
    ).fetchall()
    bound: set[str] = set()
    bindings = []
    for (source,) in sources:
        # Awake runs independently of Behaviour.enabled. Do not apply the Update capability filter.
        root = _scripted_reference(raw, source, "$host_spawn_point", "spawn_point")
        if root not in roots:
            raise ValueError(f"Account suppressor {source} has no matching native ward-controller root: {root}")
        if root in bound:
            raise ValueError(f"Multiple account suppressors bind the same encounter root: {root}")
        bound.add(root)
        bindings.append((str(source), root))
    if roots != bound:
        raise ValueError(f"Missing native account-suppressor bindings for encounter roots: {sorted(roots - bound)}")
    if not bindings:
        return result

    for fact in _CLAIM_FACTS:
        if (
            raw.execute(
                "SELECT 1 FROM code_facts WHERE fact_id = ? AND key = 'ok' AND value = 'true' AND value_type = 'bool'",
                (fact,),
            ).fetchone()
            is None
        ):
            raise ValueError(f"Account encounter requires verified code fact: {fact}")

    # code-fact: guide.gates.reliquary_sources
    # code-fact: guide.gates.reliquary_claim_awake
    quests = raw.execute("SELECT StableKey FROM Quests WHERE DBName = 'CLAIMRELIQUARY'").fetchall()
    if (
        len(quests) != 1
        or conn.execute("SELECT 1 FROM quests WHERE stable_key = ?", (quests[0][0],)).fetchone() is None
    ):
        raise ValueError("Account claiming behavior requires one existing canonical claim quest")
    quest = str(quests[0][0])
    for source, root in bindings:
        encounter = "encounter:" + source
        supports = {
            str(row[0])
            for row in conn.execute(
                "SELECT condition_stable_key FROM character_damage_releases "
                "WHERE mechanism = 'reliquary_wards' AND source_stable_key = ? "
                "AND condition_kind = 'spawn_point_cleared'",
                (root,),
            )
        }
        if root in supports:
            raise ValueError(f"An encounter root cannot also be its own support placement: {root}")
        for member in [root, *sorted(supports)]:
            if (
                conn.execute("SELECT 1 FROM character_spawns WHERE spawn_point_stable_key = ?", (member,)).fetchone()
                is None
            ):
                raise ValueError(f"Encounter member has no actual exported placement: {member}")
            result["encounter_placements"].append(
                {
                    "encounter_key": encounter,
                    "root_spawn_stable_key": root,
                    "member_spawn_stable_key": member,
                    "role": "root" if member == root else "support",
                    "context_kind": "account_claim",
                    "post_completion_role": "player_home",
                }
            )
        # Legacy quest completion promotes account state in Awake before spawn suppression.
        for scope, key in (("account", _ACCOUNT_STATE), ("character", quest)):
            result["encounter_conditions"].append(
                {
                    "encounter_key": encounter,
                    "state_scope": scope,
                    "state_key": key,
                    "required_value": "false",
                }
            )
        effects = (
            ("host_death", "account", _ACCOUNT_STATE),
            ("host_death", "character", quest),
            ("scene_awake_quest_completed", "account", _ACCOUNT_STATE),
            ("scene_awake_account_claimed", "character", quest),
        )
        # code-fact: guide.gates.reliquary_claim_saved
        # code-fact: guide.gates.reliquary_claim_loaded
        for event, scope, key in effects:
            result["encounter_completions"].append(
                {
                    "encounter_key": encounter,
                    "event_kind": event,
                    "state_scope": scope,
                    "state_key": key,
                    "result_value": "true",
                }
            )
        for event, scope, key in (
            ("scene_awake_quest_completed", "character", quest),
            ("scene_awake_account_claimed", "account", _ACCOUNT_STATE),
        ):
            result["encounter_event_conditions"].append(
                {
                    "encounter_key": encounter,
                    "event_kind": event,
                    "state_scope": scope,
                    "state_key": key,
                    "required_value": "true",
                }
            )
    return result


def process_encounters(raw: sqlite3.Connection, writer: Writer) -> None:
    """Write the shared encounter boundary after combat releases and canonical quests."""
    rows = build_encounter_rows(raw, writer.conn)
    writer.insert_encounter_placements(rows["encounter_placements"])
    writer.insert_encounter_conditions(rows["encounter_conditions"])
    writer.insert_encounter_completions(rows["encounter_completions"])
    writer.insert_encounter_event_conditions(rows["encounter_event_conditions"])
    logger.info("Encounter contexts: {} placements", len(rows["encounter_placements"]))
