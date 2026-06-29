"""Unit tests for listener-type coverage (invariant 3)."""

from __future__ import annotations

from pathlib import Path

from erenshor.application.export_surface.runner import missing_listener_types

GENERIC_UNITY_TYPES = {"GameObject", "Object", "NullScriptableObject"}


def test_missing_type_reported(tmp_path: Path) -> None:
    """A listener <T> not in the declared set is reported as missing."""
    d = tmp_path
    (d / "ItemListener.cs").write_text("class ItemListener : IAssetScanListener<Item> {}")
    (d / "FooListener.cs").write_text("class FooListener : IAssetScanListener<Foo> {}")
    assert missing_listener_types(d, {"Item"}) == ["Foo"]


def test_generic_unity_types_excluded(tmp_path: Path) -> None:
    """GameObject/Object/NullScriptableObject have no fixed data surface."""
    d = tmp_path
    (d / "BookListener.cs").write_text("class BookListener : IAssetScanListener<NullScriptableObject> {}")
    (d / "DoorListener.cs").write_text("class DoorListener : IAssetScanListener<GameObject> {}")
    assert missing_listener_types(d, set()) == []


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
