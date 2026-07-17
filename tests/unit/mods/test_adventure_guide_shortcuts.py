from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "AdventureGuide"


def test_private_renderer_shortcuts_use_shared_unity_input_with_text_guard() -> None:
    plugin = (MOD_ROOT / "src" / "Plugin.cs").read_text()

    assert "HandleKeyboardShortcuts();" in plugin
    assert "if (!GameData.PlayerTyping && !_wantsTextInput)" in plugin
    assert "if (_wantsMouseCapture || GameData.PlayerTyping)" in plugin
    assert "KeyboardShortcuts.WasPressed(_config.ToggleKey.Value, _keyboard)" in plugin
    assert "KeyboardShortcuts.WasPressed(InputManager.Journal, _keyboard)" in plugin
    assert "ImGui.IsKeyPressed" not in plugin
    assert "ToImGuiKey" not in plugin
