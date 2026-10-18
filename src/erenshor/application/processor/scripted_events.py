"""Scripted events: classified controllers that finish a quest themselves.

A code fact names the quest that each finishing rule completes, and the
controller's exported instance says where it acts. The event needs its
controller (``Activity.controller``) and the conditions of its own rule, such
as the item that lights Bellwain's torches. ``quest_routes`` turns each event
into a completion route in the event's zone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .gates import SHIVER_KEEPER_QUESTS, SHIVER_MEET_ALL, Atom, _code_fact_item, _code_fact_quest
from .hierarchy import _and

if TYPE_CHECKING:
    import sqlite3

    from .hierarchy import Activity, Groups
    from .writer import Writer

# Each finishing rule: how it names its quest and its player wording.
_RULES = {
    # code-fact: progression.siv_torch.quest
    "siv_torch_gaze": ("progression.siv_torch.quest", "Stand in the statue's gaze"),
    # code-fact: progression.bellwain.finish
    "bellwain_reveal": ("progression.bellwain.finish", "Light every torch in its colour"),
    # code-fact: guide.gates.shiver_update
    # ShiverEvent checks its quest IDs as literals, which the assert fact pins.
    "shiver_event": (None, "Meet all four keepers"),
}


def _quest(raw: sqlite3.Connection, conn: sqlite3.Connection, rule: str) -> str:
    fact = _RULES[rule][0]
    return SHIVER_MEET_ALL if fact is None else _code_fact_quest(raw, conn, fact)


def _own_conditions(raw: sqlite3.Connection, conn: sqlite3.Connection, rule: str) -> Groups:
    if rule == "bellwain_reveal":
        # code-fact: progression.bellwain.flint
        # PlayerControl lights a torch only while the player carries the flint.
        return ((Atom("item_held", _code_fact_item(raw, conn, "progression.bellwain.flint", "item_id")),),)
    if rule == "shiver_event":
        # Update finishes Meet Shivering Step once all four keeper quests are done.
        return (tuple(Atom("quest_done", quest) for quest in SHIVER_KEEPER_QUESTS),)
    return ((),)


def process_scripted_events(raw: sqlite3.Connection, writer: Writer, activity: Activity) -> int:
    """Write ``scripted_events`` and their conditions. Return the number of events."""
    conn = writer.conn
    events: list[dict[str, object]] = []
    conditions: list[dict[str, object]] = []
    for source, rule, scene in raw.execute(
        "SELECT SourceKey, RuleId, SourceScene FROM ScriptedActivators WHERE RuleId IN ("
        + ",".join("?" for _ in _RULES)
        + ") ORDER BY SourceKey",
        tuple(_RULES),
    ):
        note = _RULES[rule][1]
        groups = _and(_own_conditions(raw, conn, rule), activity.controller(source))
        if not groups:
            # A controller that can never act finishes nothing.
            continue
        zones = conn.execute("SELECT stable_key FROM zones WHERE scene_name = ?", (scene,)).fetchall()
        if len(zones) != 1:
            raise ValueError(f"Scripted event {source} has no single zone for scene {scene!r}")
        events.append(
            {
                "event_key": source,
                "quest_stable_key": _quest(raw, conn, rule),
                "rule": rule,
                "zone_stable_key": zones[0][0],
                "note": note,
            }
        )
        conditions.extend(
            {
                "event_key": source,
                "group_index": group_index,
                "atom_index": atom_index,
                "atom_kind": atom.kind,
                "atom_stable_key": atom.stable_key,
            }
            for group_index, group in enumerate(groups)
            for atom_index, atom in enumerate(group)
        )
    writer.insert_scripted_events(events)
    writer.insert_scripted_event_conditions(conditions)
    return len(events)
