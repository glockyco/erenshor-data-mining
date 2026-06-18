from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "AdventureGuide"


def test_lunaris_ui_pins_scoped_style_baseline() -> None:
    theme = (MOD_ROOT / "src" / "UI" / "Theme.cs").read_text()

    for style_var in [
        "WindowRounding",
        "ChildRounding",
        "FrameRounding",
        "PopupRounding",
        "ScrollbarRounding",
        "GrabRounding",
        "TabRounding",
        "ChildBorderSize",
        "FrameBorderSize",
        "FramePadding",
        "ItemSpacing",
        "IndentSpacing",
        "SelectableTextAlign",
    ]:
        assert f"ImGuiStyleVar.{style_var}" in theme

    assert "ImGuiStyleVar.TabRounding, 4f" in theme

    for style_col in [
        "Button",
        "ButtonHovered",
        "ButtonActive",
        "FrameBg",
        "FrameBgHovered",
        "FrameBgActive",
        "Border",
        "TitleBg",
        "TitleBgActive",
        "TitleBgCollapsed",
        "Header",
        "HeaderHovered",
        "HeaderActive",
    ]:
        assert f"ImGuiCol.{style_col}" in theme

    assert "PopStyleColor(WindowStyleColorCount)" in theme
    assert "PopStyleVar(WindowStyleVarCount)" in theme


def test_lunaris_ui_style_scope_is_exception_safe() -> None:
    theme = (MOD_ROOT / "src" / "UI" / "Theme.cs").read_text()
    guide_window = (MOD_ROOT / "src" / "UI" / "GuideWindow.cs").read_text()
    tracker_window = (MOD_ROOT / "src" / "UI" / "TrackerWindow.cs").read_text()

    assert "WindowStyleScope()" in theme
    assert "Dispose() => PopWindowStyle();" in theme

    for source in [guide_window, tracker_window]:
        assert "using var style = Theme.WindowStyleScope();" in source
        assert "finally" in source
        assert "ImGui.End();" in source
