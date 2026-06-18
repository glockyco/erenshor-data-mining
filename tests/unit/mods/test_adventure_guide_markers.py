from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "AdventureGuide"


def test_markers_use_private_billboard_not_game_nameplate() -> None:
    # The game's NamePlate.Start() dereferences a TextMeshPro the marker root
    # does not have, throwing one NullReferenceException per marker on game
    # versions that cache the nameplate text color. AG owns its billboard.
    pool = (MOD_ROOT / "src" / "Navigation" / "MarkerPool.cs").read_text()
    assert "AddComponent<NamePlate>" not in pool
    assert "AddComponent<MarkerBillboard>" in pool


def test_marker_billboard_null_guards_for_menu_scenes() -> None:
    billboard = (MOD_ROOT / "src" / "Navigation" / "MarkerBillboard.cs").read_text()
    assert "LookAt" in billboard
    # Must be safe when no player/camera exists (menu scenes), unlike the
    # game's NamePlate which assumes a live gameplay session.
    assert "GameData.PlayerControl" in billboard and "== null" in billboard
