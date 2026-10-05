"""Carry the knowledge base of simulated-player chat into the clean database.

The game ships the knowledge base as one ``KnowledgeDatabaseAsset``, and chat
answers from it alone. The entries are kept as the game ships them, also
when they are stale, because they are what chat says.

An entry keeps only the file name of the prefab it was built from
(``PrefabPath`` is ``NPCs/<file name>``), and the game never loads that path.
An entry is linked to every clean prefab character whose object name is that
file name and whose NPC name and level equal the entry's. Twin prefabs, which
share all three, link both keys. An entry whose prefab no longer exists links
none.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .writer import Writer


@dataclass(frozen=True, slots=True)
class PrefabCharacter:
    stable_key: str
    object_name: str
    npc_name: str
    level: int


def link_entry(
    entry: sqlite3.Row,
    prefabs_by_object_name: dict[str, list[PrefabCharacter]],
) -> list[str]:
    """Return the keys of the prefab characters that the entry was built from."""
    file_name = str(entry["PrefabPath"]).rpartition("/")[2]
    return [
        prefab.stable_key
        for prefab in prefabs_by_object_name.get(file_name, [])
        if prefab.npc_name == entry["NPCName"] and prefab.level == entry["Level"]
    ]


def process_knowledge_base(raw: sqlite3.Connection, writer: Writer) -> None:
    """Write the knowledge entries, their drops, and their character links."""
    prefabs_by_object_name: dict[str, list[PrefabCharacter]] = defaultdict(list)
    for row in writer.conn.execute(
        "SELECT stable_key, object_name, npc_name, level FROM characters WHERE is_prefab = 1"
    ):
        prefab = PrefabCharacter(
            stable_key=str(row["stable_key"]),
            object_name=str(row["object_name"]),
            npc_name=str(row["npc_name"] or ""),
            level=int(row["level"] or 0),
        )
        prefabs_by_object_name[prefab.object_name].append(prefab)

    entries = raw.execute(
        "SELECT Position, NPCName, ZoneName, Level, IsBoss, PrefabPath FROM KnowledgeEntries ORDER BY Position"
    ).fetchall()
    entry_rows: list[dict[str, object]] = []
    link_rows: list[dict[str, object]] = []
    for entry in entries:
        entry_rows.append(
            {
                "position": entry["Position"],
                "npc_name": entry["NPCName"],
                "zone_name": entry["ZoneName"],
                "level": entry["Level"],
                "is_boss": int(bool(entry["IsBoss"])),
                "prefab_path": entry["PrefabPath"],
            }
        )
        link_rows.extend(
            {"entry_position": entry["Position"], "character_stable_key": key}
            for key in link_entry(entry, prefabs_by_object_name)
        )
    drop_rows: list[dict[str, object]] = [
        {"entry_position": row["EntryPosition"], "position": row["Position"], "item_name": row["ItemName"]}
        for row in raw.execute(
            "SELECT EntryPosition, Position, ItemName FROM KnowledgeEntryDrops ORDER BY EntryPosition, Position"
        )
    ]

    writer.insert_knowledge_entries(entry_rows)
    writer.insert_knowledge_entry_drops(drop_rows)
    writer.insert_knowledge_entry_characters(link_rows)
    linked = len({row["entry_position"] for row in link_rows})
    logger.info(
        f"Knowledge base: {len(entry_rows)} entries, {len(drop_rows)} drops, "
        f"{linked} entries linked to {len(link_rows)} prefab characters"
    )
