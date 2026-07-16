from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "AdventureGuide"


def test_private_renderer_shortcuts_use_unity_input_with_text_guard() -> None:
    plugin = (MOD_ROOT / "src" / "Plugin.cs").read_text()

    assert "HandleKeyboardShortcuts();" in plugin
    assert "if (!GameData.PlayerTyping && !_wantsTextInput)" in plugin
    assert "if (_wantsMouseCapture || GameData.PlayerTyping)" in plugin
    assert "Input.GetKeyDown(_config.ToggleKey.Value)" in plugin
    assert "Input.GetKeyDown(InputManager.Journal)" in plugin
    assert "ImGui.IsKeyPressed" not in plugin
    assert "ToImGuiKey" not in plugin
