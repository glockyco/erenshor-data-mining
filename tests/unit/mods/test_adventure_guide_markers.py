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


def test_unlock_gated_direct_placements_skip_zone_reentry() -> None:
    source = (MOD_ROOT / "src" / "Navigation" / "WorldMarkerSystem.cs").read_text()
    direct_case = source.split("case SpawnPointBridge.SpawnState.DirectlyPlacedDead:", 1)[1].split(
        "// QuestGated, NotFound", 1
    )[0]
    lines = [line.strip() for line in direct_case.splitlines() if line.strip()]

    gate_index = lines.index("if (_data.CharacterQuestUnlocks.ContainsKey(stableKey))")
    assert lines[gate_index + 1] == "break;"
    assert any("MarkerType.ZoneReentry" in line for line in lines)
    assert "if (ShouldSuppressDirectlyPlacedRespawn(sp))" in direct_case
    assert lines.index("TryAddMarker(") > gate_index


def test_spawn_point_parses_respawn_metadata() -> None:
    source = (MOD_ROOT / "src" / "Data" / "GuideData.cs").read_text()

    assert '[JsonProperty("spawn_upon_quest_complete_stable_key")]' in source
    assert "public string? SpawnUponQuestCompleteStableKey" in source
    assert '[JsonProperty("is_directly_placed")]' in source
    assert "public bool IsDirectlyPlaced" in source
    assert '[JsonProperty("source_script")]' in source
    assert "public string? SourceScript" in source


def _directly_placed_respawn_helper() -> str:
    source = (MOD_ROOT / "src" / "Navigation" / "WorldMarkerSystem.cs").read_text()
    return source.split("private bool ShouldSuppressDirectlyPlacedRespawn", 1)[1].split(
        "// ── Loot container markers", 1
    )[0]


def test_directly_placed_scripted_spawns_suppress_zone_reentry() -> None:
    helper = _directly_placed_respawn_helper()
    assert "if (!string.IsNullOrEmpty(spawn.SourceScript))" in helper
    assert "return true;" in helper


def test_directly_placed_quest_gate_suppresses_until_resolved_and_completed() -> None:
    helper = _directly_placed_respawn_helper()

    assert "spawn.SpawnUponQuestCompleteStableKey" in helper
    assert "var gateQuest = _data.GetByStableKey(gateStableKey);" in helper
    assert "return gateQuest == null || !_state.IsCompleted(gateQuest.DBName);" in helper


def test_ordinary_directly_placed_spawns_keep_zone_reentry() -> None:
    helper = _directly_placed_respawn_helper()

    assert "if (gateStableKey == null)\n            return false;" in helper
