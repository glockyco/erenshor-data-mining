"""Keep saved teleport returns separate from serialized fixed destinations."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from .gates import _scripted_reference, _scripted_targets

if TYPE_CHECKING:
    from .writer import Writer


def build_zone_line_destination_rows(raw: sqlite3.Connection, conn: sqlite3.Connection) -> list[dict[str, object]]:
    """Resolve the actual return portal and require its native Start guard."""
    rows: list[dict[str, object]] = []
    bound: set[str] = set()
    for source, enabled in raw.execute(
        "SELECT SourceKey, ComponentIsEnabled FROM ScriptedActivators "
        "WHERE RuleId = 'reliquary_return_portal' ORDER BY SourceKey"
    ):
        if not enabled:
            continue
        # code-fact: guide.gates.reliquary_return_portal
        if (
            raw.execute(
                "SELECT 1 FROM code_facts WHERE fact_id = 'guide.gates.reliquary_return_portal' "
                "AND key = 'ok' AND value = 'true' AND value_type = 'bool'"
            ).fetchone()
            is None
        ):
            raise ValueError(f"Stored return requires a verified native Start fact: {source}")
        activity = raw.execute(
            "SELECT ReferenceKind, BoolValue FROM ScriptedActivatorReferences "
            "WHERE SourceKey = ? AND Field = '$portal_active_self'",
            (source,),
        ).fetchall()
        if len(activity) != 1 or activity[0][0] != "bool" or activity[0][1] != 0:
            raise ValueError(f"Stored return requires an initially inactive native portal reference: {source}")
        line = _scripted_reference(raw, source, "ReliqZL", "zone_line")
        _scripted_reference(raw, source, "ReliqPort", "object")
        targets = {
            key for kind, key in _scripted_targets(raw, conn, source, "ReliqPort", "enable") if kind == "zone_line"
        }
        if targets != {line}:
            raise ValueError(f"Stored return portal does not enable exactly its referenced zone line: {source}")
        if line in bound:
            raise ValueError(f"Multiple stored return controllers bind the same zone line: {line}")
        bound.add(line)
        # GameManager and CharSelectManager save and restore these fields on CurrentCharacterSlot.
        rows.append(
            {
                "zone_line_stable_key": line,
                "kind": "stored_return",
                "destination_state_key": "character_state:reliquary_return_zone",
                "landing_state_key": "character_state:reliquary_return_landing",
                "source_key": str(source),
            }
        )
    return rows


def process_zone_line_destinations(raw: sqlite3.Connection, writer: Writer) -> None:
    """Write destination semantics after clean zone lines and code facts exist."""
    writer.insert_zone_line_destination_contexts(build_zone_line_destination_rows(raw, writer.conn))
