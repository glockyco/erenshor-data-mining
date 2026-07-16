from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "AdventureGuide"


def test_lunaris_imgui_code_does_not_call_display_size_ref_getter() -> None:
    """Lunaris ships an ImGui.NET build without the ref-return DisplaySize getter."""
    ui_sources = [
        MOD_ROOT / "src" / "UI" / "GuideWindow.cs",
        MOD_ROOT / "src" / "UI" / "Theme.cs",
        MOD_ROOT / "src" / "UI" / "TrackerWindow.cs",
    ]

    for source in ui_sources:
        text = source.read_text()
        assert ".GetIO().DisplaySize" not in text


def test_vectors_use_the_netstandard_reference_without_alias_conflicts() -> None:
    csproj = (MOD_ROOT / "AdventureGuide.csproj").read_text()

    assert '<Reference Include="System.Numerics.Vectors">' not in csproj
    assert "<Aliases>Vectors</Aliases>" not in csproj

    for source in MOD_ROOT.glob("src/**/*.cs"):
        assert "extern alias Vectors" not in source.read_text()
        assert "Vectors::System.Numerics" not in source.read_text()
