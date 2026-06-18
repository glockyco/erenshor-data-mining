from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "AdventureGuide"

RENDERER_PATH = MOD_ROOT / "src" / "Rendering" / "ImGuiRenderer.cs"


def read_renderer() -> str:
    assert RENDERER_PATH.exists(), "Adventure Guide must own a private ImGuiRenderer"
    return RENDERER_PATH.read_text()


def test_private_renderer_loads_roboto_without_lunaris_font_registration() -> None:
    plugin = (MOD_ROOT / "src" / "Plugin.cs").read_text()
    renderer = read_renderer()
    csproj = (MOD_ROOT / "AdventureGuide.csproj").read_text()

    assert "AdventureGuide.Roboto-Regular.ttf" in csproj
    assert "ImGuiEx.RegisterFont" not in plugin
    assert "IFont" not in plugin
    assert "RegisterGuideFont" not in plugin
    assert "TryPushGuideFont" not in plugin
    assert "ImGuiEx.UnregisterFont" not in plugin
    assert "AdventureGuide.Roboto-Regular.ttf" in renderer
    assert "AddFontFromMemoryTTF" in renderer
    assert "ImGui.MemAlloc" in renderer
