"""Unit tests for listener-type coverage (invariant 3)."""

from __future__ import annotations

from pathlib import Path

from erenshor.application.export_surface.runner import missing_listener_types

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_missing_type_reported(tmp_path: Path) -> None:
    """A listener <T> not in the declared set is reported as missing."""
    d = tmp_path
    (d / "ItemListener.cs").write_text("class ItemListener : IAssetScanListener<Item> {}")
    (d / "FooListener.cs").write_text("class FooListener : IAssetScanListener<Foo> {}")
    assert missing_listener_types(d, {"Item"}) == ["Foo"]


def test_generic_unity_types_excluded(tmp_path: Path) -> None:
    """Unity base/catch-all listener types have no fixed data surface and are excluded."""
    d = tmp_path
    (d / "BookListener.cs").write_text("class BookListener : IAssetScanListener<NullScriptableObject> {}")
    (d / "DoorListener.cs").write_text("class DoorListener : IAssetScanListener<GameObject> {}")
    (d / "DynamicSpawnSourceListener.cs").write_text(
        "class DynamicSpawnSourceListener : IAssetScanListener<MonoBehaviour> {}"
    )
    assert missing_listener_types(d, set()) == []


def test_vith_arena_listener_declares_concrete_target() -> None:
    """VithArena is a real export surface, not a generic MonoBehaviour catch-all."""
    listener = REPO_ROOT / "src/Assets/Editor/ExportSystem/AssetScanner/Listener/VithArenaListener.cs"
    text = listener.read_text(encoding="utf-8")

    assert "IAssetScanListener<VithArena>" in text
    assert "OnAssetFound(VithArena asset)" in text
    assert "IAssetScanListener<MonoBehaviour>" not in text


def test_all_declared_returns_empty(tmp_path: Path) -> None:
    """All listener types present in the declared set -> no missing."""
    d = tmp_path
    (d / "ItemListener.cs").write_text("class ItemListener : IAssetScanListener<Item> {}")
    (d / "SpellListener.cs").write_text("class SpellListener : IAssetScanListener<Spell> {}")
    assert missing_listener_types(d, {"Item", "Spell"}) == []


def test_multiple_listeners_same_type(tmp_path: Path) -> None:
    """Two listeners for the same T don't duplicate the missing entry."""
    d = tmp_path
    (d / "ItemListener.cs").write_text("class ItemListener : IAssetScanListener<Item> {}")
    (d / "ItemBagListener.cs").write_text("class ItemBagListener : IAssetScanListener<Item> {}")
    assert missing_listener_types(d, set()) == ["Item"]
