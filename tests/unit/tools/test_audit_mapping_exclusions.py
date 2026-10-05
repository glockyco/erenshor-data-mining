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
