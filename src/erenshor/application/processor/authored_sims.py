"""Copy explicitly referenced SimPlayer prefab defaults without NPC or save semantics."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from .entities import _rename_cols, _rows

if TYPE_CHECKING:
    from .writer import Writer


def process_authored_sims(raw: sqlite3.Connection, writer: Writer) -> None:
    """Keep source references, nullable equipment positions, and authored identity exact.

    Raw character keys are provenance only. SimPlayers remain excluded from the
    ordinary character processor, including its spawn, loot, and vendor relations.
    """
    sims = _rows(raw, "SELECT * FROM AuthoredSims")
    references = _rows(raw, "SELECT * FROM AuthoredSimReferences")
    equipment = _rows(raw, "SELECT * FROM AuthoredSimEquipment")
    keys = {row["StableKey"] for row in sims}
    referenced = {row["AuthoredSimStableKey"] for row in references}
    if keys != referenced:
        raise ValueError("AuthoredSims must equal the distinct ActualSims reference set")
    sim_characters = {
        row["StableKey"]: row["NPCName"]
        for row in _rows(raw, "SELECT StableKey, NPCName FROM Characters WHERE IsSimPlayer = 1")
    }
    for row in sims:
        expected = f"authored_sim:{row['PrefabGuid']}:{row['PrefabLocalId']}"
        if row["StableKey"] != expected:
            raise ValueError(f"Authored sim key does not match its prefab reference: {row['StableKey']}")
        if row["RawCharacterStableKey"] not in sim_characters:
            raise ValueError(f"Authored sim does not resolve to a raw SimPlayer: {row['StableKey']}")
        if sim_characters[row["RawCharacterStableKey"]] != row["NPCName"]:
            raise ValueError(f"Authored sim name differs from its raw character: {row['StableKey']}")
    if any(row["AuthoredSimStableKey"] not in keys for row in equipment):
        raise ValueError("Authored sim equipment references an identity outside ActualSims")

    writer.insert_authored_sims(_rename_cols(sims))
    writer.insert_authored_sim_references(_rename_cols(references))
    writer.insert_authored_sim_equipment(_rename_cols(equipment))
