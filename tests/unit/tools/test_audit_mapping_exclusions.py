from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path
from types import ModuleType


def load_audit() -> ModuleType:
    script = Path("src/tools/audit_mapping_exclusions.py")
    spec = importlib.util.spec_from_file_location("audit_mapping_exclusions", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_renamed_copies_list_only_other_names_of_unspawned_excluded_prefabs() -> None:
    audit = load_audit()
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        "CREATE TABLE characters (stable_key TEXT, object_name TEXT, npc_name TEXT, scene TEXT, "
        "is_prefab INTEGER, is_wiki_generated INTEGER)"
    )
    db.execute("CREATE TABLE character_spawns (character_stable_key TEXT)")
    db.executemany(
        "INSERT INTO characters VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("character:watchman", "Watchman", "Watchman", None, 1, 0),
            ("character:watchman:shiveringstep:1", "Watchman", "Bridgekeeper", "ShiveringStep", 0, 1),
            ("character:night watchman", "Watchman", "Night Watchman", None, 1, 0),
            ("character:sean", "Sean Figarello", "Sean Figarello", None, 1, 0),
            ("character:sean:stowaway:1", "Sean Figarello", "Sean Figarello", "Stowaway", 0, 1),
            ("character:spawned", "Spawned Ghost", "Spawned Ghost", None, 1, 0),
            ("character:spawned:azure:1", "Spawned Ghost", "Pale Ghost", "Azure", 0, 1),
            ("character:kept", "Kept", "Kept", None, 1, 1),
            ("character:kept:azure:1", "Kept", "Kept Elsewhere", "Azure", 0, 1),
        ],
    )
    db.execute("INSERT INTO character_spawns VALUES ('character:spawned')")

    copies = audit.find_renamed_copies(db, ["character:watchman", "character:sean", "character:spawned"])

    assert [(copy["prefab_stable_key"], copy["name"], copy["scene"]) for copy in copies] == [
        ("character:watchman", "Bridgekeeper", "ShiveringStep")
    ]


def test_unclaimed_chat_names_skip_carried_renamed_and_quiet_names() -> None:
    from erenshor.application.wiki.chat_knowledge import ChatKnowledge, KnowledgeEntry
    from erenshor.application.wiki.lifecycle import ContentLifecycle, LifecyclePage, LifecycleRename

    audit = load_audit()
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE characters (stable_key TEXT, object_name TEXT, npc_name TEXT, display_name TEXT, "
        "scene TEXT, is_prefab INTEGER, is_wiki_generated INTEGER)"
    )
    db.executemany(
        "INSERT INTO characters VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("character:brute", "Summoned Brute", "Summoned: Brute", "Summoned: Brute", None, 1, 1),
            ("character:holy corpse", "Holy Corpse", "Holy Corpse", "Holy Corpse", None, 1, 0),
            ("character:wally", "Wally Waldorf", "Cecil Threbb", "Cecil Threbb", None, 1, 0),
            ("character:wally:stowaway:1", "Wally Waldorf", "Wally Waldorf", "Wally Waldorf", "Stowaway", 0, 1),
        ],
    )

    def entry(position: int, name: str, zone: str | None, key: str) -> KnowledgeEntry:
        return KnowledgeEntry(position, name, zone, 10, False, f"NPCs/{name}", (), (key,))

    knowledge = ChatKnowledge(
        [
            entry(0, "Summoned: Brute", "Duskenlight", "character:brute"),
            entry(1, "Dream Invader", "The Fernallan Portal", "character:dream invader"),
            entry(2, "Bazxzoth", None, "character:baxzxoth"),
            entry(3, "Holy Corpse", "Fernalla's Revival Plains", "character:holy corpse"),
            entry(4, "Cecil Threbb", "Stowaway's Step", "character:wally"),
        ]
    )
    lifecycle = ContentLifecycle(
        pages={
            "Holy Corpse": LifecyclePage(
                "Holy Corpse", "character:holy corpse", "unused", "character", None, None, None, "source"
            )
        },
        renames={
            "Dream Invader": LifecycleRename("Dream Invader", "character:dream invader:1", "Invader of Dreams", "s")
        },
        splits={},
    )

    unclaimed = audit.find_unclaimed_chat_names(db, knowledge, lifecycle)

    assert [(name["name"], name["lifecycle_state"]) for name in unclaimed] == [
        ("Holy Corpse", "unused"),
        ("Cecil Threbb", None),
    ]
    assert unclaimed[1]["placed_copies"] == [
        {"stable_key": "character:wally:stowaway:1", "name": "Wally Waldorf", "scene": "Stowaway"}
    ]
