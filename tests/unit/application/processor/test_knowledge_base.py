from __future__ import annotations

import sqlite3

from erenshor.application.processor.knowledge_base import PrefabCharacter, link_entry


def _entry(npc_name: str, level: int, prefab_path: str) -> sqlite3.Row:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    row: sqlite3.Row = db.execute(
        "SELECT ? AS NPCName, ? AS Level, ? AS PrefabPath", (npc_name, level, prefab_path)
    ).fetchone()
    return row


def test_entry_links_every_prefab_with_its_file_name_npc_name_and_level() -> None:
    prefabs = {
        "Leo McLaney": [
            PrefabCharacter("character:leo mclaney", "Leo McLaney", "Leo McLaney", 8),
            PrefabCharacter("character:leo mclaney:1", "Leo McLaney", "Leo McLaney", 8),
        ],
        "Brackish Crocodile Whelp": [
            PrefabCharacter("character:brackish crocodile whelp", "Brackish Crocodile Whelp", "A Brackish Croc", 8),
            PrefabCharacter(
                "character:brackish crocodile whelp:1", "Brackish Crocodile Whelp", "A Brackish Croc Whelp", 4
            ),
        ],
        "Vithean Immortal": [
            PrefabCharacter("character:vithean immortal", "Vithean Immortal", "Vithean Immortal", 42),
            PrefabCharacter("character:vithean immortal:1", "Vithean Immortal", "Vithean Immortal", 34),
        ],
    }

    assert link_entry(_entry("Leo McLaney", 8, "NPCs/Leo McLaney"), prefabs) == [
        "character:leo mclaney",
        "character:leo mclaney:1",
    ]
    assert link_entry(_entry("A Brackish Croc Whelp", 4, "NPCs/Brackish Crocodile Whelp"), prefabs) == [
        "character:brackish crocodile whelp:1"
    ]
    assert link_entry(_entry("Vithean Immortal", 34, "NPCs/Vithean Immortal"), prefabs) == [
        "character:vithean immortal:1"
    ]
    assert link_entry(_entry("Astra, Rogue of the Stars", 40, "NPCs/Astral, Guardian of Stars"), prefabs) == []
