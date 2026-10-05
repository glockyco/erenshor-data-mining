"""The clean database carries the chat knowledge base as the game ships it."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


def test_clean_knowledge_base_equals_the_raw_export(main_raw_db: Path, main_clean_db: Path) -> None:
    with closing(sqlite3.connect(main_clean_db)) as clean:
        clean.execute("ATTACH DATABASE ? AS raw", (str(main_raw_db),))
        raw_entries = clean.execute(
            "SELECT Position, NPCName, ZoneName, Level, IsBoss, PrefabPath FROM raw.KnowledgeEntries ORDER BY 1"
        ).fetchall()
        clean_entries = clean.execute(
            "SELECT position, npc_name, zone_name, level, is_boss, prefab_path FROM knowledge_entries ORDER BY 1"
        ).fetchall()
        raw_drops = clean.execute(
            "SELECT EntryPosition, Position, ItemName FROM raw.KnowledgeEntryDrops ORDER BY 1, 2"
        ).fetchall()
        clean_drops = clean.execute(
            "SELECT entry_position, position, item_name FROM knowledge_entry_drops ORDER BY 1, 2"
        ).fetchall()

    assert raw_entries, "the raw export holds no knowledge entries"
    assert clean_entries == raw_entries
    assert clean_drops == raw_drops


def test_each_knowledge_link_names_a_prefab_with_the_entry_file_name_npc_name_and_level(
    main_clean_db: Path,
) -> None:
    with closing(sqlite3.connect(main_clean_db)) as clean:
        mismatches = clean.execute(
            """
            SELECT e.position, e.npc_name, c.stable_key
            FROM knowledge_entry_characters link
            JOIN knowledge_entries e ON e.position = link.entry_position
            JOIN characters c ON c.stable_key = link.character_stable_key
            WHERE c.is_prefab != 1
               OR c.npc_name IS NOT e.npc_name
               OR c.level IS NOT e.level
               OR 'NPCs/' || c.object_name != e.prefab_path
            """
        ).fetchall()
        missing = clean.execute(
            """
            SELECT e.position, e.npc_name, c.stable_key
            FROM knowledge_entries e
            JOIN characters c
              ON c.is_prefab = 1
             AND 'NPCs/' || c.object_name = e.prefab_path
             AND c.npc_name = e.npc_name
             AND c.level = e.level
            WHERE NOT EXISTS (
                SELECT 1 FROM knowledge_entry_characters link
                WHERE link.entry_position = e.position AND link.character_stable_key = c.stable_key
            )
            """
        ).fetchall()

    assert mismatches == []
    assert missing == []
