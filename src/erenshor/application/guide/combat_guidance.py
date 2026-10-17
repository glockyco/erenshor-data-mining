"""Explain proven release mechanics without pretending they are persistent unlocks.

A trade can release one spawn, and ward or weather state can reset. These notes
therefore accompany drops rather than becoming quest-completed availability gates.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict


def combat_preparations(conn: sqlite3.Connection) -> dict[str, str]:
    """Describe enabled release alternatives for each actual character copy."""
    branches: dict[str, dict[tuple[str, str], list[sqlite3.Row]]] = defaultdict(lambda: defaultdict(list))
    for row in conn.execute("""
        SELECT character_stable_key, mechanism, source_stable_key,
               condition_kind, condition_stable_key
        FROM character_damage_releases
        WHERE can_release = 1 AND controller_enabled = 1
        ORDER BY character_stable_key, mechanism, source_stable_key,
                 condition_kind, condition_stable_key
    """):
        branches[row["character_stable_key"]][row["mechanism"], row["source_stable_key"]].append(row)

    result = {}
    for character, alternatives in branches.items():
        notes = []
        for (mechanism, _source), conditions in alternatives.items():
            note = _preparation(conn, mechanism, conditions)
            if note is None:
                # An automatic or undescribed alternative does not prove that
                # another branch's preparation is required.
                break
            if note not in notes:
                notes.append(note)
        else:
            if notes:
                result[character] = notes[0] if len(notes) == 1 else "Alternatively: " + " Or: ".join(notes)
    return result


def _preparation(conn: sqlite3.Connection, mechanism: str, conditions: list[sqlite3.Row]) -> str | None:
    references: dict[str, list[str]] = defaultdict(list)
    for row in conditions:
        references[row["condition_kind"]].append(row["condition_stable_key"])
    if mechanism == "trade_turn_in":
        variant = references["quest_variant"][0]
        items = conn.execute(
            """
            SELECT i.display_name, r.quantity
            FROM quest_required_items r
            JOIN items i ON i.stable_key = r.item_stable_key
            WHERE r.quest_variant_resource_name = ?
            ORDER BY i.display_name, i.stable_key
        """,
            (variant,),
        ).fetchall()
        if not items:
            return None
        quest = conn.execute(
            "SELECT repeatable, once_per_spawn_instance FROM quest_variants WHERE resource_name = ?", (variant,)
        ).fetchone()
        if quest is None:
            raise ValueError(f"Missing combat preparation quest variant: {variant}")
        required = ", ".join(
            row["display_name"] + (f" ({row['quantity']})" if row["quantity"] != 1 else "") for row in items
        )
        # This is the actual holder and exact resource variant, not a different
        # turn-in sharing its quest DB name or an unlock for every later spawn.
        note = f"Give it {required} to make it vulnerable."
        if quest["repeatable"] and quest["once_per_spawn_instance"]:
            note += " Repeat when it respawns."
        return note
    if mechanism == "npc_protector_weather":
        states = references["state"]
        return (
            "Vulnerable during rain."
            if states == ["raining"]
            else "Vulnerable after the rain stops."
            if states == ["dry_after_rain"]
            else None
        )
    if mechanism == "shivering_phantom_wards":
        groups: list[tuple[str, ...]] = []
        for key in references["character_dead"]:
            row = conn.execute("SELECT display_name FROM characters WHERE stable_key = ?", (key,)).fetchone()
            if row is None:
                raise ValueError(f"Missing combat preparation character: {key}")
            groups.append((row["display_name"],))
        return _defeat(groups)
    if mechanism == "reliquary_wards":
        groups = []
        for spawn in references["spawn_point_cleared"]:
            names = tuple(
                row[0]
                for row in conn.execute(
                    """
                SELECT DISTINCT c.display_name
                FROM character_spawns s JOIN characters c ON c.stable_key = s.character_stable_key
                WHERE s.spawn_point_stable_key = ?
                  AND (s.spawn_chance IS NULL OR s.spawn_chance > 0)
                ORDER BY c.display_name
            """,
                    (spawn,),
                )
            )
            if names:
                groups.append(names)
        return _defeat(groups)
    return None


def _defeat(groups: list[tuple[str, ...]]) -> str | None:
    if not groups:
        return None
    targets = []
    for candidates, quantity in Counter(groups).items():
        if len(candidates) == 1:
            targets.append(candidates[0] + (f" x{quantity}" if quantity > 1 else ""))
        else:
            targets.append(
                "one of " + "/".join(candidates) + (f" at each of {quantity} locations" if quantity > 1 else "")
            )
    return "Defeat " + " and ".join(targets) + " to make it vulnerable."
