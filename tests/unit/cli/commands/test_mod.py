"""Targeted tests for mod command setup prerequisites."""

from __future__ import annotations

from pathlib import Path

from erenshor.cli.commands.mod import REQUIRED_DLLS


def test_required_dlls_cover_adventure_guide_unity_modules() -> None:
    assert "UnityEngine.IMGUIModule.dll" in REQUIRED_DLLS
    assert "UnityEngine.TextRenderingModule.dll" in REQUIRED_DLLS
    assert "UnityEngine.AIModule.dll" in REQUIRED_DLLS
    assert "UnityEngine.PhysicsModule.dll" in REQUIRED_DLLS


def test_adventure_guide_uses_lunaris_loader() -> None:
    from erenshor.cli.commands.mod import MODS

    ag = MODS["adventure-guide"]
    assert ag["loader"] == "lunaris"
    assert "thunderstore" not in ag
    assert "ImGui.NET.dll" in ag["lunaris_dlls"]
    assert "Newtonsoft.Json.dll" in ag["lunaris_dlls"]


def test_lunaris_mods_deploy_to_plugins_not_bepinex(tmp_path: Path) -> None:
    from erenshor.cli.commands.mod import _get_deploy_target_dir

    target, label, copy_pdb = _get_deploy_target_dir("adventure-guide", tmp_path, scripts=False)
    assert target == tmp_path / "plugins"
    assert copy_pdb is False
    assert "Lunaris" in label


def test_next_calver_revision_starts_at_zero_for_new_day() -> None:
    from erenshor.cli.commands.mod import _next_calver_revision

    assert _next_calver_revision("2026.618", None) == "2026.618.0"
    assert _next_calver_revision("2026.618", "2026.617.3") == "2026.618.0"


def test_next_calver_revision_increments_within_same_day() -> None:
    from erenshor.cli.commands.mod import _next_calver_revision

    assert _next_calver_revision("2026.618", "2026.618.0") == "2026.618.1"
    assert _next_calver_revision("2026.618", "2026.618.4") == "2026.618.5"


def test_latest_calver_for_prefix_picks_max_revision_order_independent() -> None:
    from erenshor.cli.commands.mod import _latest_calver_for_prefix

    versions = ["2026.617.0", "2026.618.0", "2026.618.2", "2026.618.1"]
    assert _latest_calver_for_prefix(versions, "2026.618") == "2026.618.2"
    assert _latest_calver_for_prefix(versions, "2026.619") is None
    assert _latest_calver_for_prefix([], "2026.618") is None
