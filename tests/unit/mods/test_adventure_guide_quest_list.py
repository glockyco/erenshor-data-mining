from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "AdventureGuide"


def test_quest_list_uses_padded_marker_column_for_tracked_rows() -> None:
    panel = (MOD_ROOT / "src" / "UI" / "QuestListPanel.cs").read_text()

    assert "QuestListMarkerColumnWidth" in panel
    assert "QuestListMarkerStartX" in panel
    assert "ImGui.GetStyle()" in panel
    assert "style.FramePadding.X" in panel
    assert "style.ItemInnerSpacing.X" in panel
    assert 'ImGui.CalcTextSize("00").X' not in panel
    assert "var contentStart = ImGui.GetCursorPos()" in panel
    assert "ImGui.SetCursorPos(new Vector2(0f, contentStart.Y))" in panel
    assert "ImGui.GetContentRegionAvail().X + contentStart.X" in panel
    assert "var markerStart = QuestListMarkerStartX(contentStart.X)" in panel
    assert "ImGui.SetCursorPos(new Vector2(markerStart, contentStart.Y))" in panel
    assert "ImGui.SetCursorPos(new Vector2(markerStart + markerWidth, contentStart.Y))" in panel
    assert "prefix = isTracked" not in panel
