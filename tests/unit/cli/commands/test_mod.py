"""Targeted tests for mod command setup prerequisites."""

from __future__ import annotations

from erenshor.cli.commands.mod import REQUIRED_DLLS


def test_required_dlls_cover_adventure_guide_unity_modules() -> None:
    assert "UnityEngine.IMGUIModule.dll" in REQUIRED_DLLS
    assert "UnityEngine.TextRenderingModule.dll" in REQUIRED_DLLS
    assert "UnityEngine.AIModule.dll" in REQUIRED_DLLS
    assert "UnityEngine.PhysicsModule.dll" in REQUIRED_DLLS
