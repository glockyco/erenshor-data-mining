"""Compare the authored export with serialized ActualSims references, never a name list."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from erenshor.application.processor.entities import _snake
from erenshor.infrastructure.config import load_config

_ROOT = Path(__file__).resolve().parents[2]


def _documents(path: Path) -> dict[str, str]:
    parts = re.split(r"(?m)^--- !u!\d+ &(-?\d+)\n", path.read_text())
    return dict(zip(parts[1::2], parts[2::2], strict=True))


def _field(body: str, name: str) -> str:
    match = re.search(rf"(?m)^  {re.escape(name)}: *(.*)$", body)
    assert match is not None, name
    value = match[1].strip()
    if value.startswith('"'):
        return str(json.loads(value))
    if value.startswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def _guid(meta: Path) -> str:
    match = re.search(r"(?m)^guid: ([a-f0-9]+)$", meta.read_text())
    assert match is not None, meta
    return match[1]


def test_authored_sim_reference_set_and_defaults_match_sources(main_raw_db: Path, main_clean_db: Path) -> None:
    variant = load_config().variants["main"]
    project = variant.resolved_unity_project(_ROOT)
    assets = project / "Assets"
    scene_path = assets / "Scenes" / "LoadScene.unity"
    scene_guid = _guid(scene_path.with_suffix(".unity.meta"))
    script_guids = {
        name: _guid(next(assets.rglob(f"{name}.cs.meta")))
        for name in ("SimPlayerMngr", "Character", "NPC", "Stats", "Inventory", "SimPlayer")
    }
    managers = {
        local_id: body
        for local_id, body in _documents(scene_path).items()
        if script_guids["SimPlayerMngr"] in body and "\n  ActualSims:" in body
    }
    assert managers, "LoadScene must contain serialized SimPlayerMngr references"
    expected = []
    for local_id, body in managers.items():
        tail = body.split("\n  ActualSims:", 1)[1]
        block = re.split(r"\n  [A-Za-z_]", tail, maxsplit=1)[0]
        refs = re.findall(r"(?m)^  - \{fileID: (-?\d+), guid: ([a-f0-9]+), type: \d+\}$", block)
        assert refs, "ActualSims must contain resolvable prefab references"
        expected.extend(
            (f"GlobalObjectId_V1-2-{scene_guid}-{local_id}-0", index, f"authored_sim:{guid}:{file_id}")
            for index, (file_id, guid) in enumerate(refs)
        )
    with (
        sqlite3.connect(f"file:{main_raw_db}?mode=ro", uri=True) as raw,
        sqlite3.connect(f"file:{main_clean_db}?mode=ro", uri=True) as clean,
    ):
        raw.row_factory = sqlite3.Row
        clean.row_factory = sqlite3.Row
        actual = [
            tuple(row)
            for row in raw.execute(
                "SELECT SourceComponentKey, ReferenceIndex, AuthoredSimStableKey FROM AuthoredSimReferences"
            )
        ]
        assert sorted(actual) == sorted(expected)
        sims = list(raw.execute("SELECT * FROM AuthoredSims"))
        assert {row["StableKey"] for row in sims} == {row[2] for row in expected}
        asset_sources = {_guid(meta): meta.with_suffix("") for meta in assets.rglob("*.asset.meta")}
        for sim in sims:
            prefab = project / sim["PrefabPath"]
            assert _guid(prefab.with_suffix(".prefab.meta")) == sim["PrefabGuid"]
            documents = _documents(prefab)
            root = documents[str(sim["PrefabLocalId"])]
            assert _field(root, "m_Name") == sim["ObjectName"]
            components = [
                documents[file_id] for file_id in re.findall(r"(?m)^  - component: \{fileID: (-?\d+)\}$", root)
            ]
            components_by_type = {}
            for name, script_guid in script_guids.items():
                if name == "SimPlayerMngr":
                    continue
                matches = [body for body in components if script_guid in body]
                assert len(matches) == 1, (sim["StableKey"], name)
                components_by_type[name] = matches[0]
            assert _field(components_by_type["NPC"], "NPCName") == sim["NPCName"]
            assert int(_field(components_by_type["Stats"], "Level")) == sim["SeedLevel"]
            assert int(_field(components_by_type["Inventory"], "isMale")) == sim["SeedIsMale"]
            class_guid = re.search(r"guid: ([a-f0-9]+)", _field(components_by_type["Stats"], "CharacterClass"))
            assert class_guid is not None
            assert _field(asset_sources[class_guid[1]].read_text(), "ClassName") == sim["SeedClassName"]
            inventory = components_by_type["Inventory"].split("\n  EquippedItems:", 1)[1]
            inventory = re.split(r"\n  [A-Za-z_]", inventory, maxsplit=1)[0]
            expected_equipment = []
            for position, reference in enumerate(re.findall(r"(?m)^  - (\{.*\})$", inventory)):
                item_guid = re.search(r"guid: ([a-f0-9]+)", reference)
                item_key = None
                if item_guid is not None:
                    item_name = _field(asset_sources[item_guid[1]].read_text(), "m_Name")
                    keys = raw.execute("SELECT StableKey FROM Items WHERE ResourceName = ?", (item_name,)).fetchall()
                    assert len(keys) == 1, item_name
                    item_key = keys[0][0]
                else:
                    assert reference == "{fileID: 0}"
                expected_equipment.append((position, item_key))
            assert [
                tuple(row)
                for row in raw.execute(
                    "SELECT Position, ItemStableKey FROM AuthoredSimEquipment "
                    "WHERE AuthoredSimStableKey = ? ORDER BY Position",
                    (sim["StableKey"],),
                )
            ] == expected_equipment
            for source, column in (
                ("HairName", "SeedHairName"),
                ("HairColor", "SeedHairColor"),
                ("SkinColor", "SeedSkinColor"),
                ("IsGMCharacter", "IsGMCharacter"),
                ("Rival", "Rival"),
                ("SkillLevel", "SeedSkillLevel"),
            ):
                value = _field(components_by_type["SimPlayer"], source)
                if source == "SkillLevel":
                    assert sim[column] == pytest.approx(float(value))
                else:
                    assert (value if source == "HairName" else int(value)) == sim[column]
            source_character = raw.execute(
                "SELECT Guid, NPCName, IsSimPlayer FROM Characters WHERE StableKey = ?",
                (sim["RawCharacterStableKey"],),
            ).fetchone()
            assert tuple(source_character) == (sim["PrefabGuid"], sim["NPCName"], 1)
            assert (
                clean.execute(
                    "SELECT count(*) FROM characters WHERE stable_key = ?", (sim["RawCharacterStableKey"],)
                ).fetchone()[0]
                == 0
            )
        for raw_table, clean_table in (
            ("AuthoredSims", "authored_sims"),
            ("AuthoredSimReferences", "authored_sim_references"),
            ("AuthoredSimEquipment", "authored_sim_equipment"),
        ):
            raw_rows = [
                {_snake(key): value for key, value in dict(row).items()}
                for row in raw.execute(f"SELECT * FROM {raw_table}")
            ]
            clean_rows = [dict(row) for row in clean.execute(f"SELECT * FROM {clean_table}")]
            assert sorted(raw_rows, key=str) == sorted(clean_rows, key=str)
        assert list(clean.execute("PRAGMA foreign_key_check")) == []
