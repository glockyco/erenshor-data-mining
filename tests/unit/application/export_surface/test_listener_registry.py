"""Focused, Unity-free contracts for the shared export listener registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from erenshor.application.export_surface.listener_inventory import (
    ListenerInventoryEntry,
    read_listener_inventory,
    validate_listener_inventory,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
REGISTRY = REPO_ROOT / "src" / "Assets" / "Editor" / "ExportSystem" / "ExportListenerRegistry.cs"
BATCH = REPO_ROOT / "src" / "Assets" / "Editor" / "ExportBatch.cs"
EDITOR = REPO_ROOT / "src" / "Assets" / "Editor" / "ExportSystem" / "AssetScanner" / "AssetScannerExporterWindow.cs"

EXPECTED_KEYS = {
    "gameconstants",
    "teleportlocs",
    "secretpassages",
    "wishingwells",
    "questactivations",
    "ascensions",
    "books",
    "classes",
    "quests",
    "skills",
    "spells",
    "stances",
    "guildtopics",
    "worldfactions",
    "zoneatlasentries",
    "items",
    "achievementtriggers",
    "doors",
    "forges",
    "itembags",
    "classstartingitems",
    "loottables",
    "arenarounds",
    "itemdrops",
    "miningnodes",
    "spawnpoints",
    "treasurehunting",
    "treasurelocs",
    "waters",
    "zoneannounces",
    "zonelines",
    "characters",
}


def test_registry_inventory_is_ordered_and_complete() -> None:
    entries = read_listener_inventory(REGISTRY)
    assert {entry.key for entry in entries} == EXPECTED_KEYS
    assert len(entries) == len(EXPECTED_KEYS)
    assert all(entry.key == entry.key.casefold() for entry in entries)
    assert all(entry.label.strip() for entry in entries)
    assert {entry.channel for entry in entries} == {"Null", "GameObject", "ScriptableObject", "Component"}
    validate_listener_inventory(entries)


def test_dependencies_encode_items_and_characters_ordering() -> None:
    entries = read_listener_inventory(REGISTRY)
    by_key = {entry.key: entry for entry in entries}
    assert by_key["items"].dependencies == ("spells",)
    assert by_key["characters"].dependencies == ("spawnpoints",)
    assert [entry.key for entry in entries].index("spells") < [entry.key for entry in entries].index("items")
    assert [entry.key for entry in entries].index("spawnpoints") < [entry.key for entry in entries].index("characters")


def test_spawn_registration_preserves_multi_listener_order_and_return_value() -> None:
    registry = REGISTRY.read_text(encoding="utf-8")
    assert registry.index("new SpawnPointListener") < registry.index("new SpawnPointTriggerListener")
    assert registry.index("new SpawnPointTriggerListener") < registry.index("new DynamicSpawnSourceListener")
    assert "_dynamicSpawnListener = result.DynamicSpawnListener" in BATCH.read_text(encoding="utf-8")


def test_inventory_validation_rejects_unknown_and_misordered_dependencies() -> None:
    entries = (
        ListenerInventoryEntry("first", "First", "Component", ()),
        ListenerInventoryEntry("second", "Second", "Component", ("first",)),
    )
    with pytest.raises(ValueError, match="unknown listener keys"):
        validate_listener_inventory(entries, {"missing"})
    with pytest.raises(ValueError, match="later key"):
        validate_listener_inventory(
            (
                ListenerInventoryEntry("first", "First", "Component", ("second",)),
                ListenerInventoryEntry("second", "Second", "Component", ()),
            )
        )
    with pytest.raises(ValueError, match="selected dependencies"):
        validate_listener_inventory(entries, {"second"})


def test_entrypoints_consume_registry_without_own_listener_inventory() -> None:
    batch = BATCH.read_text(encoding="utf-8")
    editor = EDITOR.read_text(encoding="utf-8")
    assert "ExportListenerRegistry.Register" in batch
    assert "ExportListenerRegistry.Register" in editor
    assert "new Dictionary<string, Action>" not in batch
    assert "RegisterComponentListener(new" not in editor
    assert "RegisterScriptableObjectListener(new" not in editor
    assert "RegisterGameObjectListener(new" not in editor
