"""Focused behavioral tests for the immutable maintained-mod catalog."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from erenshor.application.mods.catalog import iter_mods, lookup_mod, public_mods


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
