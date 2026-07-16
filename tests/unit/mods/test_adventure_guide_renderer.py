import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "AdventureGuide"

RENDERER_PATH = MOD_ROOT / "src" / "Rendering" / "ImGuiRenderer.cs"


def read_renderer() -> str:
    assert RENDERER_PATH.exists(), "Adventure Guide must own a private ImGuiRenderer"
    return RENDERER_PATH.read_text()


def test_adventure_guide_owns_private_imgui_context() -> None:
    plugin = (MOD_ROOT / "src" / "Plugin.cs").read_text()
    renderer = read_renderer()

    assert re.search(r"\bImGuiRenderer\?\s+\w*imgui\w*\s*;", plugin, re.IGNORECASE)
    assert re.search(r"\bvoid\s+OnGUI\s*\(", plugin)
    assert "public override void OnImGuiDraw()" not in plugin
    assert "ImGui.CreateContext()" in renderer
    assert renderer.count("ImGui.GetCurrentContext()") >= 2
    assert renderer.count("ImGui.SetCurrentContext(") >= 4


def test_private_renderer_uses_full_screen_display_for_overlays() -> None:
    renderer = read_renderer()

    assert re.search(r"\.DisplaySize\s*=\s*new\s+\w+\s*\(\s*Screen\.width\s*,\s*Screen\.height\s*\)", renderer)
    assert "Matrix4x4.Ortho" in renderer
    assert "screenW" in renderer
    assert "screenH" in renderer


def test_private_renderer_uses_lunaris_imgui_binaries() -> None:
    csproj = (MOD_ROOT / "AdventureGuide.csproj").read_text()
    renderer = read_renderer()

    assert "LoadLibrary" not in renderer
    assert "FreeLibrary" not in renderer
    assert "AdventureGuide.cimgui.dll" not in renderer
    assert "cimgui.dll" not in csproj
    assert '<Reference Include="ImGui.NET">' in csproj
    assert "lib/lunaris/ImGui.NET.dll" in csproj
