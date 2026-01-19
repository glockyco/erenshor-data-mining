"""Unit tests for csproj generator.

These tests verify the .csproj and .sln file generation for LSP support.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from erenshor.infrastructure.csproj_generator import (
    SUPPRESSED_WARNINGS,
    UnityPaths,
    _collect_all_dlls,
    _collect_editor_dlls,
    _collect_package_dlls,
    _parse_csproj_references,
    _relative_path,
    discover_mod_projects,
    generate_editor_scripts_csproj,
    generate_game_scripts_csproj,
    generate_root_solution,
    generate_solution_file,
)


class TestUnityPaths:
    """Test UnityPaths class for resolving Unity installation directories."""

    def test_editor_managed_path_macos(self, tmp_path: Path) -> None:
        """Test editor_managed returns correct path on macOS."""
        unity_exe = tmp_path / "Unity.app" / "Contents" / "MacOS" / "Unity"
        unity_exe.parent.mkdir(parents=True)
        unity_exe.touch()

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "darwin"):
            paths = UnityPaths(executable=unity_exe)
            assert paths.editor_managed == tmp_path / "Unity.app" / "Contents" / "Managed"

    def test_editor_managed_path_windows(self, tmp_path: Path) -> None:
        """Test editor_managed returns correct path on Windows."""
        unity_exe = tmp_path / "Editor" / "Unity.exe"
        unity_exe.parent.mkdir(parents=True)
        unity_exe.touch()

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "win32"):
            paths = UnityPaths(executable=unity_exe)
            assert paths.editor_managed == tmp_path / "Editor" / "Data" / "Managed"

    def test_mono_runtime_path_macos(self, tmp_path: Path) -> None:
        """Test mono_runtime returns correct path on macOS."""
        unity_exe = tmp_path / "Unity.app" / "Contents" / "MacOS" / "Unity"
        unity_exe.parent.mkdir(parents=True)
        unity_exe.touch()

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "darwin"):
            paths = UnityPaths(executable=unity_exe)
            expected = tmp_path / "Unity.app" / "Contents" / "MonoBleedingEdge" / "lib" / "mono" / "unityjit-macos"
            assert paths.mono_runtime == expected

    def test_mono_runtime_path_windows(self, tmp_path: Path) -> None:
        """Test mono_runtime returns correct path on Windows."""
        unity_exe = tmp_path / "Editor" / "Unity.exe"
        unity_exe.parent.mkdir(parents=True)
        unity_exe.touch()

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "win32"):
            paths = UnityPaths(executable=unity_exe)
            expected = tmp_path / "Editor" / "Data" / "MonoBleedingEdge" / "lib" / "mono" / "unityjit-win32"
            assert paths.mono_runtime == expected

    def test_mono_runtime_path_linux(self, tmp_path: Path) -> None:
        """Test mono_runtime returns correct path on Linux."""
        unity_exe = tmp_path / "Editor" / "Unity"
        unity_exe.parent.mkdir(parents=True)
        unity_exe.touch()

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "linux"):
            paths = UnityPaths(executable=unity_exe)
            expected = tmp_path / "Editor" / "Data" / "MonoBleedingEdge" / "lib" / "mono" / "unityjit-linux"
            assert paths.mono_runtime == expected

    def test_validate_raises_for_missing_executable(self, tmp_path: Path) -> None:
        """Test validate raises FileNotFoundError for missing executable."""
        unity_exe = tmp_path / "nonexistent" / "Unity"
        paths = UnityPaths(executable=unity_exe)

        with pytest.raises(FileNotFoundError, match="Unity executable not found"):
            paths.validate()

    def test_validate_raises_for_missing_managed_folder(self, tmp_path: Path) -> None:
        """Test validate raises FileNotFoundError for missing Managed folder."""
        unity_exe = tmp_path / "Unity.app" / "Contents" / "MacOS" / "Unity"
        unity_exe.parent.mkdir(parents=True)
        unity_exe.touch()

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "darwin"):
            paths = UnityPaths(executable=unity_exe)
            with pytest.raises(FileNotFoundError, match="Unity Editor Managed folder not found"):
                paths.validate()

    def test_validate_raises_for_missing_mono_folder(self, tmp_path: Path) -> None:
        """Test validate raises FileNotFoundError for missing mono runtime folder."""
        unity_exe = tmp_path / "Unity.app" / "Contents" / "MacOS" / "Unity"
        unity_exe.parent.mkdir(parents=True)
        unity_exe.touch()
        (tmp_path / "Unity.app" / "Contents" / "Managed").mkdir(parents=True)

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "darwin"):
            paths = UnityPaths(executable=unity_exe)
            with pytest.raises(FileNotFoundError, match="Unity Mono runtime folder not found"):
                paths.validate()

    def test_validate_succeeds_with_all_folders(self, tmp_path: Path) -> None:
        """Test validate succeeds when all required folders exist."""
        unity_exe = tmp_path / "Unity.app" / "Contents" / "MacOS" / "Unity"
        unity_exe.parent.mkdir(parents=True)
        unity_exe.touch()
        (tmp_path / "Unity.app" / "Contents" / "Managed").mkdir(parents=True)
        (tmp_path / "Unity.app" / "Contents" / "MonoBleedingEdge" / "lib" / "mono" / "unityjit-macos").mkdir(
            parents=True
        )

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "darwin"):
            paths = UnityPaths(executable=unity_exe)
            paths.validate()  # Should not raise

    def test_from_executable_creates_and_validates(self, tmp_path: Path) -> None:
        """Test from_executable creates instance and validates."""
        unity_exe = tmp_path / "Unity.app" / "Contents" / "MacOS" / "Unity"
        unity_exe.parent.mkdir(parents=True)
        unity_exe.touch()
        (tmp_path / "Unity.app" / "Contents" / "Managed").mkdir(parents=True)
        (tmp_path / "Unity.app" / "Contents" / "MonoBleedingEdge" / "lib" / "mono" / "unityjit-macos").mkdir(
            parents=True
        )

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "darwin"):
            paths = UnityPaths.from_executable(unity_exe)
            assert paths.executable == unity_exe

    def test_from_executable_raises_for_invalid_paths(self, tmp_path: Path) -> None:
        """Test from_executable raises for invalid installation."""
        unity_exe = tmp_path / "nonexistent" / "Unity"

        with pytest.raises(FileNotFoundError):
            UnityPaths.from_executable(unity_exe)


class TestCollectAllDlls:
    """Test collecting all DLLs from a directory."""

    def test_collects_all_dlls(self, tmp_path: Path) -> None:
        """Test that all .dll files are collected."""
        dll_dir = tmp_path / "dlls"
        dll_dir.mkdir()
        (dll_dir / "UnityEngine.dll").touch()
        (dll_dir / "System.dll").touch()
        (dll_dir / "SomePlugin.dll").touch()
        (dll_dir / "notadll.txt").touch()  # Should be ignored

        result = _collect_all_dlls(dll_dir)

        names = [p.name for p in result]
        assert "UnityEngine.dll" in names
        assert "System.dll" in names
        assert "SomePlugin.dll" in names
        assert "notadll.txt" not in names
        assert len(result) == 3

    def test_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test that empty list is returned for nonexistent directory."""
        result = _collect_all_dlls(tmp_path / "nonexistent")
        assert result == []

    def test_returns_sorted_list(self, tmp_path: Path) -> None:
        """Test that results are sorted by name."""
        dll_dir = tmp_path / "dlls"
        dll_dir.mkdir()
        (dll_dir / "Zebra.dll").touch()
        (dll_dir / "Apple.dll").touch()
        (dll_dir / "Mango.dll").touch()

        result = _collect_all_dlls(dll_dir)

        names = [p.name for p in result]
        assert names == ["Apple.dll", "Mango.dll", "Zebra.dll"]


class TestCollectEditorDlls:
    """Test collecting Unity Editor DLLs."""

    def test_collects_only_unity_editor_dlls(self, tmp_path: Path) -> None:
        """Test that only UnityEditor*.dll files are collected."""
        managed_dir = tmp_path / "Managed"
        managed_dir.mkdir()
        (managed_dir / "UnityEditor.dll").touch()
        (managed_dir / "UnityEditor.CoreModule.dll").touch()
        (managed_dir / "UnityEngine.dll").touch()  # Should NOT be collected
        (managed_dir / "System.dll").touch()  # Should NOT be collected

        result = _collect_editor_dlls(managed_dir)

        names = [p.name for p in result]
        assert "UnityEditor.dll" in names
        assert "UnityEditor.CoreModule.dll" in names
        assert "UnityEngine.dll" not in names
        assert "System.dll" not in names

    def test_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test that empty list is returned for nonexistent directory."""
        result = _collect_editor_dlls(tmp_path / "nonexistent")
        assert result == []


class TestCollectPackageDlls:
    """Test collecting DLLs from NuGet packages."""

    def test_collects_dlls_from_netstandard_folders(self, tmp_path: Path) -> None:
        """Test that DLLs are found in nested package structure."""
        packages_dir = tmp_path / "Packages"
        packages_dir.mkdir()

        # Create package structure
        sqlite_pkg = packages_dir / "sqlite-net-pcl.1.9.172" / "lib" / "netstandard2.0"
        sqlite_pkg.mkdir(parents=True)
        (sqlite_pkg / "SQLite-net.dll").touch()

        json_pkg = packages_dir / "Newtonsoft.Json.13.0.3" / "lib" / "netstandard2.0"
        json_pkg.mkdir(parents=True)
        (json_pkg / "Newtonsoft.Json.dll").touch()

        result = _collect_package_dlls(packages_dir)

        names = [p.name for p in result]
        assert "SQLite-net.dll" in names
        assert "Newtonsoft.Json.dll" in names

    def test_ignores_dlls_outside_netstandard_folder(self, tmp_path: Path) -> None:
        """Test that DLLs outside lib/netstandard2.0 are ignored."""
        packages_dir = tmp_path / "Packages"
        packages_dir.mkdir()

        # DLL at wrong location
        wrong_loc = packages_dir / "pkg" / "lib" / "net45"
        wrong_loc.mkdir(parents=True)
        (wrong_loc / "Wrong.dll").touch()

        result = _collect_package_dlls(packages_dir)

        assert result == []

    def test_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test that empty list is returned for nonexistent directory."""
        result = _collect_package_dlls(tmp_path / "nonexistent")
        assert result == []


class TestParseCsprojReferences:
    """Test parsing DLL references from csproj files."""

    def test_parses_references_with_hintpath(self, tmp_path: Path) -> None:
        """Test that Reference elements with HintPath are parsed correctly."""
        csproj_dir = tmp_path / "project"
        csproj_dir.mkdir()
        csproj_path = csproj_dir / "Test.csproj"

        # Create DLLs that are referenced
        dlls_dir = tmp_path / "dlls"
        dlls_dir.mkdir()
        (dlls_dir / "UnityEngine.dll").touch()
        (dlls_dir / "System.dll").touch()

        csproj_content = """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Reference Include="UnityEngine">
      <HintPath>../dlls/UnityEngine.dll</HintPath>
    </Reference>
    <Reference Include="System">
      <HintPath>../dlls/System.dll</HintPath>
    </Reference>
  </ItemGroup>
</Project>
"""
        csproj_path.write_text(csproj_content)

        result = _parse_csproj_references(csproj_path)

        names = [p.name for p in result]
        assert "UnityEngine.dll" in names
        assert "System.dll" in names
        assert len(result) == 2

    def test_ignores_references_without_hintpath(self, tmp_path: Path) -> None:
        """Test that Reference elements without HintPath are ignored."""
        csproj_path = tmp_path / "Test.csproj"
        csproj_content = """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Reference Include="System" />
    <Reference Include="System.Core" />
  </ItemGroup>
</Project>
"""
        csproj_path.write_text(csproj_content)

        result = _parse_csproj_references(csproj_path)

        assert result == []

    def test_ignores_nonexistent_dlls(self, tmp_path: Path) -> None:
        """Test that references to nonexistent DLLs are ignored."""
        csproj_path = tmp_path / "Test.csproj"
        csproj_content = """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Reference Include="Missing">
      <HintPath>../nonexistent/Missing.dll</HintPath>
    </Reference>
  </ItemGroup>
</Project>
"""
        csproj_path.write_text(csproj_content)

        result = _parse_csproj_references(csproj_path)

        assert result == []

    def test_returns_empty_for_nonexistent_csproj(self, tmp_path: Path) -> None:
        """Test that empty list is returned for nonexistent csproj."""
        result = _parse_csproj_references(tmp_path / "nonexistent.csproj")
        assert result == []

    def test_returns_empty_for_invalid_xml(self, tmp_path: Path) -> None:
        """Test that empty list is returned for invalid XML."""
        csproj_path = tmp_path / "Test.csproj"
        csproj_path.write_text("not valid xml <<<<")

        result = _parse_csproj_references(csproj_path)

        assert result == []

    def test_returns_sorted_list(self, tmp_path: Path) -> None:
        """Test that results are sorted by name."""
        csproj_dir = tmp_path / "project"
        csproj_dir.mkdir()
        csproj_path = csproj_dir / "Test.csproj"

        dlls_dir = tmp_path / "dlls"
        dlls_dir.mkdir()
        (dlls_dir / "Zebra.dll").touch()
        (dlls_dir / "Apple.dll").touch()
        (dlls_dir / "Mango.dll").touch()

        csproj_content = """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Reference Include="Zebra">
      <HintPath>../dlls/Zebra.dll</HintPath>
    </Reference>
    <Reference Include="Apple">
      <HintPath>../dlls/Apple.dll</HintPath>
    </Reference>
    <Reference Include="Mango">
      <HintPath>../dlls/Mango.dll</HintPath>
    </Reference>
  </ItemGroup>
</Project>
"""
        csproj_path.write_text(csproj_content)

        result = _parse_csproj_references(csproj_path)

        names = [p.name for p in result]
        assert names == ["Apple.dll", "Mango.dll", "Zebra.dll"]


class TestRelativePath:
    """Test relative path calculation."""

    def test_simple_relative_path(self, tmp_path: Path) -> None:
        """Test relative path within same tree."""
        from_dir = tmp_path / "a" / "b"
        to_path = tmp_path / "a" / "c" / "file.dll"
        from_dir.mkdir(parents=True)
        to_path.parent.mkdir(parents=True)
        to_path.touch()

        result = _relative_path(from_dir, to_path)

        assert result == Path("../c/file.dll")

    def test_deeply_nested_relative_path(self, tmp_path: Path) -> None:
        """Test relative path with multiple levels up."""
        from_dir = tmp_path / "a" / "b" / "c" / "d"
        to_path = tmp_path / "x" / "y" / "file.dll"
        from_dir.mkdir(parents=True)
        to_path.parent.mkdir(parents=True)
        to_path.touch()

        result = _relative_path(from_dir, to_path)

        assert result == Path("../../../../x/y/file.dll")

    def test_same_directory(self, tmp_path: Path) -> None:
        """Test relative path to file in same directory."""
        from_dir = tmp_path / "a"
        to_path = tmp_path / "a" / "file.dll"
        from_dir.mkdir(parents=True)
        to_path.touch()

        result = _relative_path(from_dir, to_path)

        assert result == Path("file.dll")


class TestGenerateGameScriptsCsproj:
    """Test game scripts .csproj file generation."""

    def test_generates_csproj_file(self, tmp_path: Path) -> None:
        """Test that .csproj file is generated with correct structure."""
        scripts_dir = tmp_path / "Scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "SomeScript.cs").touch()

        managed_dir = tmp_path / "Managed"
        managed_dir.mkdir()
        (managed_dir / "UnityEngine.dll").touch()
        (managed_dir / "mscorlib.dll").touch()

        plugins_dir = tmp_path / "Plugins"
        plugins_dir.mkdir()
        (plugins_dir / "SomePlugin.dll").touch()

        result = generate_game_scripts_csproj(scripts_dir, managed_dir, plugins_dir)

        assert result.exists()
        assert result.name == "Assembly-CSharp.csproj"

        content = result.read_text()
        assert "<TargetFramework>netstandard2.1</TargetFramework>" in content
        assert "<LangVersion>9.0</LangVersion>" in content
        assert "UnityEngine.dll" in content
        assert "mscorlib.dll" in content
        assert "SomePlugin.dll" in content

    def test_includes_warning_suppressions(self, tmp_path: Path) -> None:
        """Test that warning suppressions are included."""
        scripts_dir = tmp_path / "Scripts"
        scripts_dir.mkdir(parents=True)
        managed_dir = tmp_path / "Managed"
        managed_dir.mkdir()
        (managed_dir / "UnityEngine.dll").touch()
        plugins_dir = tmp_path / "Plugins"

        result = generate_game_scripts_csproj(scripts_dir, managed_dir, plugins_dir)
        content = result.read_text()

        for warning in SUPPRESSED_WARNINGS:
            assert warning in content

    def test_raises_for_missing_scripts_dir(self, tmp_path: Path) -> None:
        """Test that FileNotFoundError is raised for missing scripts directory."""
        with pytest.raises(FileNotFoundError, match="Scripts directory not found"):
            generate_game_scripts_csproj(
                tmp_path / "nonexistent",
                tmp_path / "Managed",
                tmp_path / "Plugins",
            )

    def test_raises_for_no_dlls(self, tmp_path: Path) -> None:
        """Test that ValueError is raised when no DLLs are found."""
        scripts_dir = tmp_path / "Scripts"
        scripts_dir.mkdir(parents=True)
        managed_dir = tmp_path / "Managed"
        managed_dir.mkdir()  # Empty
        plugins_dir = tmp_path / "Plugins"

        with pytest.raises(ValueError, match="No DLLs found"):
            generate_game_scripts_csproj(scripts_dir, managed_dir, plugins_dir)

    def test_uses_relative_paths(self, tmp_path: Path) -> None:
        """Test that generated references use relative paths."""
        scripts_dir = tmp_path / "project" / "Assets" / "Scripts"
        scripts_dir.mkdir(parents=True)
        managed_dir = tmp_path / "game" / "Managed"
        managed_dir.mkdir(parents=True)
        (managed_dir / "UnityEngine.dll").touch()
        plugins_dir = tmp_path / "project" / "Assets" / "Plugins"
        plugins_dir.mkdir(parents=True)

        result = generate_game_scripts_csproj(scripts_dir, managed_dir, plugins_dir)
        content = result.read_text()

        # Paths should be relative, not absolute
        assert str(tmp_path) not in content
        assert "<HintPath>" in content
        assert ".." in content


def _create_game_structure(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    """Create a mock game folder structure for testing.

    Returns:
        Tuple of (game_scripts_csproj, game_managed_dir, plugins_dir, packages_dir, variant_dir)
    """
    # Create variant structure
    variant_dir = tmp_path / "variants" / "main"

    # Game managed folder with DLLs
    game_managed_dir = variant_dir / "game" / "Erenshor_Data" / "Managed"
    game_managed_dir.mkdir(parents=True)
    (game_managed_dir / "UnityEngine.dll").touch()
    (game_managed_dir / "mscorlib.dll").touch()
    (game_managed_dir / "System.dll").touch()

    # Unity project structure
    exported_project = variant_dir / "unity" / "ExportedProject"
    scripts_dir = exported_project / "Assets" / "Scripts" / "Assembly-CSharp"
    scripts_dir.mkdir(parents=True)
    game_scripts_csproj = scripts_dir / "Assembly-CSharp.csproj"

    plugins_dir = exported_project / "Assets" / "Plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "SomePlugin.dll").touch()

    packages_dir = exported_project / "Assets" / "Packages"
    sqlite_pkg = packages_dir / "sqlite-net-pcl.1.9.172" / "lib" / "netstandard2.0"
    sqlite_pkg.mkdir(parents=True)
    (sqlite_pkg / "SQLite-net.dll").touch()

    # Create a proper csproj with Reference elements that _parse_csproj_references can parse.
    # The paths are relative from the csproj location to the managed/plugins folders.
    managed_relative = _relative_path(scripts_dir, game_managed_dir)
    plugins_relative = _relative_path(scripts_dir, plugins_dir)

    csproj_content = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netstandard2.1</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <Reference Include="UnityEngine">
      <HintPath>{managed_relative}/UnityEngine.dll</HintPath>
    </Reference>
    <Reference Include="mscorlib">
      <HintPath>{managed_relative}/mscorlib.dll</HintPath>
    </Reference>
    <Reference Include="System">
      <HintPath>{managed_relative}/System.dll</HintPath>
    </Reference>
    <Reference Include="SomePlugin">
      <HintPath>{plugins_relative}/SomePlugin.dll</HintPath>
    </Reference>
  </ItemGroup>
</Project>
"""
    game_scripts_csproj.write_text(csproj_content)

    return game_scripts_csproj, game_managed_dir, plugins_dir, packages_dir, variant_dir


def _create_unity_paths(tmp_path: Path) -> UnityPaths:
    """Create a mock UnityPaths instance for testing."""
    unity_exe = tmp_path / "Unity.app" / "Contents" / "MacOS" / "Unity"
    unity_exe.parent.mkdir(parents=True)
    unity_exe.touch()

    managed_dir = tmp_path / "Unity.app" / "Contents" / "Managed"
    managed_dir.mkdir(parents=True)

    mono_dir = tmp_path / "Unity.app" / "Contents" / "MonoBleedingEdge" / "lib" / "mono" / "unityjit-macos"
    mono_dir.mkdir(parents=True)

    return UnityPaths(executable=unity_exe)


class TestGenerateEditorScriptsCsproj:
    """Test Editor .csproj file generation."""

    def test_generates_editor_csproj_file(self, tmp_path: Path) -> None:
        """Test that Editor .csproj file is generated with correct structure."""
        game_csproj, _, _, _, _ = _create_game_structure(tmp_path)

        editor_scripts_dir = tmp_path / "Editor"
        editor_scripts_dir.mkdir(parents=True)
        (editor_scripts_dir / "SomeEditorScript.cs").touch()

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "darwin"):
            unity_paths = _create_unity_paths(tmp_path)
            (unity_paths.editor_managed / "UnityEditor.dll").touch()

            result = generate_editor_scripts_csproj(editor_scripts_dir, unity_paths, game_csproj)

        assert result.exists()
        assert result.name == "Assembly-CSharp-Editor.csproj"

        content = result.read_text()
        assert "<TargetFramework>netstandard2.1</TargetFramework>" in content
        assert "UnityEditor.dll" in content
        # Should include game DLLs
        assert "UnityEngine.dll" in content
        assert "mscorlib.dll" in content
        # Should include package DLLs
        assert "SQLite-net.dll" in content

    def test_includes_project_reference(self, tmp_path: Path) -> None:
        """Test that game scripts project reference is always included."""
        game_csproj, _, _, _, _ = _create_game_structure(tmp_path)

        editor_scripts_dir = tmp_path / "Editor"
        editor_scripts_dir.mkdir(parents=True)

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "darwin"):
            unity_paths = _create_unity_paths(tmp_path)
            (unity_paths.editor_managed / "UnityEditor.dll").touch()

            result = generate_editor_scripts_csproj(editor_scripts_dir, unity_paths, game_csproj)
            content = result.read_text()

        assert "<ProjectReference" in content
        assert "Assembly-CSharp.csproj" in content

    def test_raises_for_missing_editor_scripts_dir(self, tmp_path: Path) -> None:
        """Test that FileNotFoundError is raised for missing editor scripts directory."""
        game_csproj, _, _, _, _ = _create_game_structure(tmp_path)

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "darwin"):
            unity_paths = _create_unity_paths(tmp_path)
            (unity_paths.editor_managed / "UnityEditor.dll").touch()

            with pytest.raises(FileNotFoundError, match="Editor scripts directory not found"):
                generate_editor_scripts_csproj(tmp_path / "nonexistent", unity_paths, game_csproj)

    def test_raises_for_missing_game_csproj(self, tmp_path: Path) -> None:
        """Test that FileNotFoundError is raised for missing game scripts csproj."""
        editor_scripts_dir = tmp_path / "Editor"
        editor_scripts_dir.mkdir(parents=True)

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "darwin"):
            unity_paths = _create_unity_paths(tmp_path)
            (unity_paths.editor_managed / "UnityEditor.dll").touch()

            with pytest.raises(FileNotFoundError, match="Game scripts csproj not found"):
                generate_editor_scripts_csproj(editor_scripts_dir, unity_paths, tmp_path / "nonexistent.csproj")

    def test_uses_relative_paths(self, tmp_path: Path) -> None:
        """Test that generated references use relative paths."""
        game_csproj, _, _, _, _ = _create_game_structure(tmp_path)

        editor_scripts_dir = tmp_path / "project" / "Assets" / "Editor"
        editor_scripts_dir.mkdir(parents=True)

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "darwin"):
            unity_paths = _create_unity_paths(tmp_path)
            (unity_paths.editor_managed / "UnityEditor.dll").touch()

            result = generate_editor_scripts_csproj(editor_scripts_dir, unity_paths, game_csproj)
            content = result.read_text()

        # Paths should be relative, not absolute
        assert str(tmp_path) not in content
        assert "<HintPath>" in content
        assert ".." in content

    def test_includes_dlls_from_all_sources(self, tmp_path: Path) -> None:
        """Test that DLLs from all game folders are included."""
        game_csproj, _, _, _, _ = _create_game_structure(tmp_path)

        editor_scripts_dir = tmp_path / "Editor"
        editor_scripts_dir.mkdir(parents=True)

        with patch("erenshor.infrastructure.csproj_generator.sys.platform", "darwin"):
            unity_paths = _create_unity_paths(tmp_path)
            (unity_paths.editor_managed / "UnityEditor.dll").touch()
            (unity_paths.editor_managed / "UnityEditor.CoreModule.dll").touch()

            result = generate_editor_scripts_csproj(editor_scripts_dir, unity_paths, game_csproj)
            content = result.read_text()

        # Unity Editor DLLs
        assert "UnityEditor.dll" in content
        assert "UnityEditor.CoreModule.dll" in content
        # Game Managed DLLs
        assert "mscorlib.dll" in content
        assert "System.dll" in content
        # Plugin DLLs
        assert "SomePlugin.dll" in content
        # Package DLLs
        assert "SQLite-net.dll" in content


class TestGenerateSolutionFile:
    """Test .sln file generation."""

    def test_generates_sln_file(self, tmp_path: Path) -> None:
        """Test that .sln file is generated."""
        csproj_path = tmp_path / "Project" / "Assembly-CSharp.csproj"
        csproj_path.parent.mkdir(parents=True)
        csproj_path.write_text("<Project />")
        solution_dir = tmp_path

        result = generate_solution_file(solution_dir, csproj_path)

        assert result.exists()
        assert result.suffix == ".sln"
        content = result.read_text()
        assert "Assembly-CSharp" in content

    def test_custom_solution_name(self, tmp_path: Path) -> None:
        """Test that custom solution name is used."""
        csproj_path = tmp_path / "Project" / "MyProject.csproj"
        csproj_path.parent.mkdir(parents=True)
        csproj_path.write_text("<Project />")

        result = generate_solution_file(tmp_path, csproj_path, solution_name="CustomName")

        assert result.name == "CustomName.sln"

    def test_raises_for_missing_csproj(self, tmp_path: Path) -> None:
        """Test that FileNotFoundError is raised for missing csproj."""
        with pytest.raises(FileNotFoundError, match="Project file not found"):
            generate_solution_file(tmp_path, tmp_path / "nonexistent.csproj")

    def test_contains_project_configuration(self, tmp_path: Path) -> None:
        """Test that solution contains project configuration."""
        csproj_path = tmp_path / "Project" / "Assembly-CSharp.csproj"
        csproj_path.parent.mkdir(parents=True)
        csproj_path.write_text("<Project />")

        result = generate_solution_file(tmp_path, csproj_path)
        content = result.read_text()

        assert "Debug|Any CPU" in content
        assert "Release|Any CPU" in content

    def test_uses_relative_path_to_csproj(self, tmp_path: Path) -> None:
        """Test that solution uses relative path to .csproj."""
        project_dir = tmp_path / "src" / "project"
        project_dir.mkdir(parents=True)
        csproj_path = project_dir / "Assembly-CSharp.csproj"
        csproj_path.write_text("<Project />")

        result = generate_solution_file(tmp_path, csproj_path)
        content = result.read_text()

        # Should not contain absolute path
        assert str(tmp_path) not in content
        # Should contain relative path
        assert "src" in content

    def test_includes_additional_projects(self, tmp_path: Path) -> None:
        """Test that additional projects are included in the solution."""
        main_csproj = tmp_path / "Main" / "Main.csproj"
        main_csproj.parent.mkdir(parents=True)
        main_csproj.write_text("<Project />")

        additional_csproj = tmp_path / "Additional" / "Additional.csproj"
        additional_csproj.parent.mkdir(parents=True)
        additional_csproj.write_text("<Project />")

        result = generate_solution_file(tmp_path, main_csproj, additional_projects=[additional_csproj])
        content = result.read_text()

        assert "Main" in content
        assert "Additional" in content

    def test_skips_nonexistent_additional_projects(self, tmp_path: Path) -> None:
        """Test that nonexistent additional projects are silently skipped."""
        main_csproj = tmp_path / "Main" / "Main.csproj"
        main_csproj.parent.mkdir(parents=True)
        main_csproj.write_text("<Project />")

        nonexistent = tmp_path / "Nonexistent" / "Nonexistent.csproj"

        result = generate_solution_file(tmp_path, main_csproj, additional_projects=[nonexistent])
        content = result.read_text()

        assert "Main" in content
        assert "Nonexistent" not in content

    def test_multiple_additional_projects(self, tmp_path: Path) -> None:
        """Test that multiple additional projects are included."""
        main_csproj = tmp_path / "Main" / "Main.csproj"
        main_csproj.parent.mkdir(parents=True)
        main_csproj.write_text("<Project />")

        projects = []
        for name in ["ProjectA", "ProjectB", "ProjectC"]:
            csproj = tmp_path / name / f"{name}.csproj"
            csproj.parent.mkdir(parents=True)
            csproj.write_text("<Project />")
            projects.append(csproj)

        result = generate_solution_file(tmp_path, main_csproj, additional_projects=projects)
        content = result.read_text()

        assert "Main" in content
        assert "ProjectA" in content
        assert "ProjectB" in content
        assert "ProjectC" in content


class TestDiscoverModProjects:
    """Test mod project discovery."""

    def test_discovers_mod_projects(self, tmp_path: Path) -> None:
        """Test that mod projects are discovered."""
        mods_dir = tmp_path / "mods"
        mod_csproj = mods_dir / "MyMod" / "MyMod.csproj"
        mod_csproj.parent.mkdir(parents=True)
        mod_csproj.write_text("<Project />")

        mod_projects, test_projects = discover_mod_projects(mods_dir)

        assert len(mod_projects) == 1
        assert mod_projects[0].name == "MyMod.csproj"
        assert len(test_projects) == 0

    def test_discovers_test_projects(self, tmp_path: Path) -> None:
        """Test that test projects are categorized correctly."""
        mods_dir = tmp_path / "mods"

        # Test project in tests folder
        test_csproj = mods_dir / "MyMod" / "tests" / "MyMod.Tests" / "MyMod.Tests.csproj"
        test_csproj.parent.mkdir(parents=True)
        test_csproj.write_text("<Project />")

        mod_projects, test_projects = discover_mod_projects(mods_dir)

        assert len(mod_projects) == 0
        assert len(test_projects) == 1
        assert test_projects[0].name == "MyMod.Tests.csproj"

    def test_skips_build_artifacts(self, tmp_path: Path) -> None:
        """Test that obj/bin folders are skipped."""
        mods_dir = tmp_path / "mods"

        # Project in obj folder (should be skipped)
        obj_csproj = mods_dir / "MyMod" / "obj" / "Debug" / "SomeFile.csproj"
        obj_csproj.parent.mkdir(parents=True)
        obj_csproj.write_text("<Project />")

        mod_projects, test_projects = discover_mod_projects(mods_dir)

        assert len(mod_projects) == 0
        assert len(test_projects) == 0

    def test_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test that empty lists are returned for nonexistent directory."""
        mod_projects, test_projects = discover_mod_projects(tmp_path / "nonexistent")

        assert mod_projects == []
        assert test_projects == []

    def test_discovers_multiple_mods(self, tmp_path: Path) -> None:
        """Test that multiple mod projects are discovered."""
        mods_dir = tmp_path / "mods"

        for name in ["ModA", "ModB", "ModC"]:
            csproj = mods_dir / name / f"{name}.csproj"
            csproj.parent.mkdir(parents=True)
            csproj.write_text("<Project />")

        mod_projects, _ = discover_mod_projects(mods_dir)

        names = [p.stem for p in mod_projects]
        assert "ModA" in names
        assert "ModB" in names
        assert "ModC" in names


class TestGenerateRootSolution:
    """Test root solution file generation."""

    def test_generates_root_solution(self, tmp_path: Path) -> None:
        """Test that root solution is generated with projects."""
        csproj = tmp_path / "Mod" / "Mod.csproj"
        csproj.parent.mkdir(parents=True)
        csproj.write_text("<Project />")

        result = generate_root_solution(
            solution_path=tmp_path / "Root.sln",
            game_script_projects={},
            mod_projects=[csproj],
            test_projects=[],
        )

        assert result.exists()
        content = result.read_text()
        assert "Mod" in content

    def test_includes_multiple_variants(self, tmp_path: Path) -> None:
        """Test that multiple game script variants are included."""
        main_csproj = tmp_path / "main" / "Assembly-CSharp.csproj"
        main_csproj.parent.mkdir(parents=True)
        main_csproj.write_text("<Project />")

        playtest_csproj = tmp_path / "playtest" / "Assembly-CSharp.csproj"
        playtest_csproj.parent.mkdir(parents=True)
        playtest_csproj.write_text("<Project />")

        result = generate_root_solution(
            solution_path=tmp_path / "Root.sln",
            game_script_projects={"main": main_csproj, "playtest": playtest_csproj},
            mod_projects=[],
            test_projects=[],
        )

        content = result.read_text()
        assert "main" in content
        assert "playtest" in content

    def test_includes_mod_projects(self, tmp_path: Path) -> None:
        """Test that mod projects are included."""
        mod_csproj = tmp_path / "MyMod" / "MyMod.csproj"
        mod_csproj.parent.mkdir(parents=True)
        mod_csproj.write_text("<Project />")

        result = generate_root_solution(
            solution_path=tmp_path / "Root.sln",
            game_script_projects={},
            mod_projects=[mod_csproj],
            test_projects=[],
        )

        content = result.read_text()
        assert "MyMod" in content

    def test_includes_test_projects(self, tmp_path: Path) -> None:
        """Test that test projects are included."""
        test_csproj = tmp_path / "MyMod.Tests" / "MyMod.Tests.csproj"
        test_csproj.parent.mkdir(parents=True)
        test_csproj.write_text("<Project />")

        result = generate_root_solution(
            solution_path=tmp_path / "Root.sln",
            game_script_projects={},
            mod_projects=[],
            test_projects=[test_csproj],
        )

        content = result.read_text()
        assert "MyMod.Tests" in content

    def test_creates_solution_folders(self, tmp_path: Path) -> None:
        """Test that solution folders are created."""
        mod_csproj = tmp_path / "MyMod" / "MyMod.csproj"
        mod_csproj.parent.mkdir(parents=True)
        mod_csproj.write_text("<Project />")

        result = generate_root_solution(
            solution_path=tmp_path / "Root.sln",
            game_script_projects={},
            mod_projects=[mod_csproj],
            test_projects=[],
        )

        content = result.read_text()
        # Check for solution folder GUID type
        assert "2150E333-8FDC-42A3-9474-1A3956D46DE8" in content

    def test_raises_for_no_projects(self, tmp_path: Path) -> None:
        """Test that ValueError is raised when no projects are provided."""
        with pytest.raises(ValueError, match="No projects provided"):
            generate_root_solution(
                solution_path=tmp_path / "Root.sln",
                game_script_projects={},
                mod_projects=[],
                test_projects=[],
            )

    def test_uses_relative_paths(self, tmp_path: Path) -> None:
        """Test that relative paths are used in solution."""
        mod_csproj = tmp_path / "src" / "mods" / "MyMod" / "MyMod.csproj"
        mod_csproj.parent.mkdir(parents=True)
        mod_csproj.write_text("<Project />")

        result = generate_root_solution(
            solution_path=tmp_path / "Root.sln",
            game_script_projects={},
            mod_projects=[mod_csproj],
            test_projects=[],
        )

        content = result.read_text()
        # Should not contain absolute path
        assert str(tmp_path) not in content
        # Should contain relative path
        assert "src" in content
