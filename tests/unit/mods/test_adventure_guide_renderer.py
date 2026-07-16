import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "AdventureGuide"

RENDERER_PATH = MOD_ROOT / "src" / "Rendering" / "ImGuiRenderer.cs"


def read_renderer() -> str:
    assert RENDERER_PATH.exists(), "Adventure Guide must own a private ImGuiRenderer"
    return RENDERER_PATH.read_text()


def test_adventure_guide_owns_private_imgui_context() -> None:
    runtime = (MOD_ROOT / "src" / "Plugin.cs").read_text()
    renderer = read_renderer()

    assert re.search(r"class\s+AdventureGuideRuntime\b", runtime)
    assert re.search(r"\bImGuiRenderer\?\s+\w*imgui\w*\s*;", runtime, re.IGNORECASE)
    assert re.search(r"\bvoid\s+Draw\s*\(", runtime)
    assert "public override void OnImGuiDraw()" not in runtime
    assert "ImGui.CreateContext()" in renderer
    assert renderer.count("ImGui.GetCurrentContext()") >= 2
    assert renderer.count("ImGui.SetCurrentContext(") >= 4


def test_native_adapters_forward_unity_render_callbacks() -> None:
    for loader in ("BepInEx", "Lunaris"):
        adapter = (MOD_ROOT / "src" / f"Plugin.{loader}.cs").read_text()
        assert "private void OnGUI() => _runtime?.Draw();" in adapter
        assert "private void Update() => _runtime?.Tick();" in adapter


def test_loader_specific_imgui_dependencies_are_explicit() -> None:
    csproj = (MOD_ROOT / "AdventureGuide.csproj").read_text()
    renderer = read_renderer()

    assert "LoadLibrary" not in renderer
    assert "FreeLibrary" not in renderer
    assert '<Reference Include="ImGui.NET">' in csproj
    assert "lib/lunaris/ImGui.NET.dll" in csproj
    assert '<PackageReference Include="ImGui.NET" Version="1.88.0"' in csproj
    assert "win-x64/native/cimgui.dll" in csproj
