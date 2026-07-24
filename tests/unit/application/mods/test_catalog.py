"""Focused behavioral tests for the immutable maintained-mod catalog."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from erenshor.application.mods.artifacts import ModArtifactSpec
from erenshor.application.mods.catalog import artifact_specs, iter_mods, lookup_mod, public_mods


def test_catalog_preserves_declared_order_and_exact_inventory() -> None:
    expected = (
        "interactive-map-companion",
        "justice-for-f7",
        "sprint",
        "map-tile-capture",
        "adventure-guide",
    )
    assert tuple(definition.mod_id for definition in iter_mods()) == expected


def test_lookup_and_public_selection_are_explicit_and_ordered() -> None:
    assert lookup_mod("sprint").display_name == "Sprint"
    assert tuple(definition.mod_id for definition in public_mods()) == (
        "interactive-map-companion",
        "justice-for-f7",
        "sprint",
        "adventure-guide",
    )
    with pytest.raises(KeyError):
        lookup_mod("interactive-maps-companion")


def test_definitions_and_catalog_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        lookup_mod("sprint").loaders = ("lunaris",)


def test_artifact_specs_preserve_identity_order_and_distribution_metadata() -> None:
    expected = (
        ModArtifactSpec(
            "interactive-map-companion",
            Path("src/mods/InteractiveMapCompanion"),
            "Interactive Map Companion",
            "InteractiveMapCompanion.dll",
            ("bepinex", "lunaris"),
            True,
            "WoW_Much/InteractiveMapCompanion",
            ("InteractiveMapCompanion.dll",),
        ),
        ModArtifactSpec(
            "justice-for-f7",
            Path("src/mods/JusticeForF7"),
            "Justice for F7",
            "JusticeForF7.dll",
            ("bepinex", "lunaris"),
            True,
            "WoW_Much/JusticeForF7",
            ("JusticeForF7.dll",),
        ),
        ModArtifactSpec(
            "sprint",
            Path("src/mods/Sprint"),
            "Sprint",
            "Sprint.dll",
            ("bepinex", "lunaris"),
            True,
            "WoW_Much/Sprint",
            ("Sprint.dll",),
        ),
        ModArtifactSpec(
            "map-tile-capture",
            Path("src/mods/MapTileCapture"),
            "Map Tile Capture",
            "MapTileCapture.dll",
            ("bepinex", "lunaris"),
            False,
            None,
        ),
        ModArtifactSpec(
            "adventure-guide",
            Path("src/mods/AdventureGuide"),
            "Adventure Guide",
            "AdventureGuide.dll",
            ("bepinex", "lunaris"),
            True,
            "WoW_Much/AdventureGuide",
            (
                "AdventureGuide.dll",
                "ImGui.NET.dll",
                "Newtonsoft.Json.dll",
                "System.Numerics.Vectors.dll",
                "System.Runtime.CompilerServices.Unsafe.dll",
                "cimgui.dll",
            ),
        ),
    )
    assert artifact_specs() == expected
