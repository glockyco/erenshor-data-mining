"""Generate .csproj and .sln files for IDE/LSP support.

This module creates project files that enable IDE features like "Find References"
and "Go to Definition" for the decompiled game scripts and mod projects.
The generated game script projects are not meant for actual compilation -
they exist solely to enable C# language server features in editors like
Zed, VS Code, or Rider.
"""

import sys
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# Warning codes to suppress in decompiled code
SUPPRESSED_WARNINGS = [
    "CS0114",  # member hides inherited member
    "CS0108",  # member hides inherited member (with new keyword suggestion)
    "CS0649",  # field never assigned
    "CS0169",  # field never used
    "CS8618",  # non-nullable field not initialized
    "CS0414",  # field assigned but never used
    "CS0067",  # event never used
    "CS0626",  # extern method without DllImport
    "CS0219",  # variable assigned but never used
    "CS0162",  # unreachable code
]


@dataclass
class UnityPaths:
    """Resolves Unity Editor paths from the executable location.

    Unity Editor has a complex directory structure with DLLs spread across
    multiple locations. This class encapsulates the platform-specific logic
    for locating these directories.

    On macOS:
        executable: .../Unity.app/Contents/MacOS/Unity
        managed:    .../Unity.app/Contents/Managed/
        mono:       .../Unity.app/Contents/MonoBleedingEdge/lib/mono/unityjit-macos/

    On Windows:
        executable: .../Editor/Unity.exe
        managed:    .../Editor/Data/Managed/
        mono:       .../Editor/Data/MonoBleedingEdge/lib/mono/unityjit-win32/

    On Linux:
        executable: .../Editor/Unity
        managed:    .../Editor/Data/Managed/
        mono:       .../Editor/Data/MonoBleedingEdge/lib/mono/unityjit-linux/
    """

    executable: Path

    @property
    def editor_managed(self) -> Path:
        """Path to Unity Editor's Managed folder (UnityEditor.dll, UnityEngine.dll, etc.)."""
        if sys.platform == "darwin":
            # macOS: .../Unity.app/Contents/MacOS/Unity -> .../Unity.app/Contents/Managed/
            return self.executable.parent.parent / "Managed"
        # Windows/Linux: .../Editor/Unity.exe -> .../Editor/Data/Managed/
        return self.executable.parent / "Data" / "Managed"

    @property
    def mono_runtime(self) -> Path:
        """Path to Mono runtime folder (mscorlib.dll, System.dll, etc.)."""
        if sys.platform == "darwin":
            base = self.executable.parent.parent / "MonoBleedingEdge" / "lib" / "mono"
            platform_suffix = "unityjit-macos"
        elif sys.platform == "win32":
            base = self.executable.parent / "Data" / "MonoBleedingEdge" / "lib" / "mono"
            platform_suffix = "unityjit-win32"
        else:
            base = self.executable.parent / "Data" / "MonoBleedingEdge" / "lib" / "mono"
            platform_suffix = "unityjit-linux"

        return base / platform_suffix

    def validate(self) -> None:
        """Validate that all required Unity paths exist.

        Raises:
            FileNotFoundError: If the Unity executable or required directories don't exist.
        """
        if not self.executable.exists():
            msg = f"Unity executable not found: {self.executable}"
            raise FileNotFoundError(msg)

        if not self.editor_managed.exists():
            msg = (
                f"Unity Editor Managed folder not found: {self.editor_managed}\n"
                f"Expected location based on executable: {self.executable}"
            )
            raise FileNotFoundError(msg)

        if not self.mono_runtime.exists():
            msg = (
                f"Unity Mono runtime folder not found: {self.mono_runtime}\n"
                f"Expected location based on executable: {self.executable}"
            )
            raise FileNotFoundError(msg)

    @classmethod
    def from_executable(cls, executable: Path) -> "UnityPaths":
        """Create UnityPaths from executable path and validate.

        Args:
            executable: Path to the Unity executable.

        Returns:
            Validated UnityPaths instance.

        Raises:
            FileNotFoundError: If paths don't exist.
        """
        paths = cls(executable=executable)
        paths.validate()
        return paths


def generate_game_scripts_csproj(
    scripts_dir: Path,
    managed_dlls_dir: Path,
    plugins_dir: Path,
) -> Path:
    """Generate Assembly-CSharp.csproj for LSP support.

    Creates a .csproj file that references Unity and plugin DLLs, enabling
    C# language servers to provide navigation and analysis features.

    Args:
        scripts_dir: Path to Assembly-CSharp scripts directory.
        managed_dlls_dir: Path to game's Managed folder containing Unity DLLs.
        plugins_dir: Path to Assets/Plugins folder containing plugin DLLs.

    Returns:
        Path to the generated .csproj file.

    Raises:
        FileNotFoundError: If scripts_dir doesn't exist.
        ValueError: If no DLLs are found to reference.
    """
    if not scripts_dir.exists():
        msg = f"Scripts directory not found: {scripts_dir}"
        raise FileNotFoundError(msg)

    csproj_path = scripts_dir / "Assembly-CSharp.csproj"

    # Collect ALL DLLs from game folders (no pattern filtering)
    # Filter out Assembly-CSharp.dll since this csproj IS Assembly-CSharp
    managed_dlls = [dll for dll in _collect_all_dlls(managed_dlls_dir) if dll.name != "Assembly-CSharp.dll"]
    plugin_dlls = _collect_all_dlls(plugins_dir)

    if not managed_dlls and not plugin_dlls:
        msg = f"No DLLs found in {managed_dlls_dir} or {plugins_dir}"
        raise ValueError(msg)

    # Calculate relative paths from csproj location
    managed_relative = _relative_path(csproj_path.parent, managed_dlls_dir)
    plugins_relative = _relative_path(csproj_path.parent, plugins_dir)

    # Generate csproj content
    content = _generate_csproj_content(
        managed_dlls=managed_dlls,
        plugin_dlls=plugin_dlls,
        managed_relative=managed_relative,
        plugins_relative=plugins_relative,
    )

    csproj_path.write_text(content)
    return csproj_path


def generate_editor_scripts_csproj(
    editor_scripts_dir: Path,
    unity_paths: UnityPaths,
    game_scripts_csproj: Path,
) -> Path:
    """Generate Assembly-CSharp-Editor.csproj for Editor scripts LSP support.

    Creates a .csproj file for Unity Editor scripts that references:
    - Unity Editor DLLs (UnityEditor*.dll from Unity installation)
    - All DLLs referenced by the game scripts csproj (parsed from XML)
    - Package DLLs from Assets/Packages (for Editor-specific deps like SQLite)
    - The game scripts project (via ProjectReference for Go to Definition)

    By parsing the game csproj's references instead of scanning folders, we:
    - Reuse the working, tested DLL set from the game csproj
    - Avoid conflicts (we filter out Assembly-CSharp.dll, using ProjectReference instead)
    - Automatically adapt if game csproj references change

    Args:
        editor_scripts_dir: Path to Editor scripts directory.
        unity_paths: UnityPaths instance with validated Unity installation paths.
        game_scripts_csproj: Path to Assembly-CSharp.csproj (required).

    Returns:
        Path to the generated .csproj file.

    Raises:
        FileNotFoundError: If editor_scripts_dir or game_scripts_csproj doesn't exist.
        ValueError: If no DLLs are found.
    """
    if not editor_scripts_dir.exists():
        msg = f"Editor scripts directory not found: {editor_scripts_dir}"
        raise FileNotFoundError(msg)

    if not game_scripts_csproj.exists():
        msg = f"Game scripts csproj not found: {game_scripts_csproj}"
        raise FileNotFoundError(msg)

    csproj_path = editor_scripts_dir / "Assembly-CSharp-Editor.csproj"

    # Derive Packages folder from csproj location (4 levels up to ExportedProject)
    exported_project_dir = game_scripts_csproj.parent.parent.parent.parent
    game_packages_dir = exported_project_dir / "Assets" / "Packages"

    # Collect Unity Editor DLLs (the one thing game csproj doesn't have)
    editor_dlls = _collect_editor_dlls(unity_paths.editor_managed)

    # Parse game csproj to get its DLL references (already working, no conflicts)
    # Filter out Assembly-CSharp.dll since we use ProjectReference to source code
    game_dll_paths = [p for p in _parse_csproj_references(game_scripts_csproj) if p.name != "Assembly-CSharp.dll"]

    # Collect package DLLs for Editor-specific dependencies (e.g., SQLite)
    package_dlls = _collect_package_dlls(game_packages_dir)

    if not editor_dlls and not game_dll_paths:
        msg = (
            f"No DLLs found.\n"
            f"  Unity Editor managed: {unity_paths.editor_managed}\n"
            f"  Game csproj references: {game_scripts_csproj}"
        )
        raise ValueError(msg)

    # Combine all DLL sources, then dedupe by filename (first occurrence wins)
    all_dll_paths = editor_dlls + game_dll_paths + package_dlls
    unique_dll_paths = _dedupe_dlls_by_name(all_dll_paths)

    # Generate csproj content
    game_scripts_relative = _relative_path(csproj_path.parent, game_scripts_csproj)
    content = _generate_editor_csproj_content_from_paths(
        csproj_dir=csproj_path.parent,
        dll_paths=unique_dll_paths,
        game_scripts_relative=game_scripts_relative,
    )

    csproj_path.write_text(content)
    return csproj_path


def generate_solution_file(
    solution_dir: Path,
    csproj_path: Path,
    solution_name: str = "Erenshor-GameScripts",
    additional_projects: list[Path] | None = None,
) -> Path:
    """Generate .sln file referencing one or more .csproj files.

    Creates a Visual Studio solution file that helps IDEs discover
    the project(s) when opening the folder.

    Args:
        solution_dir: Directory where the .sln file will be created.
        csproj_path: Path to the main .csproj file to reference.
        solution_name: Name for the solution file (without extension).
        additional_projects: Optional list of additional .csproj paths to include.

    Returns:
        Path to the generated .sln file.

    Raises:
        FileNotFoundError: If csproj_path doesn't exist.
    """
    if not csproj_path.exists():
        msg = f"Project file not found: {csproj_path}"
        raise FileNotFoundError(msg)

    solution_path = solution_dir / f"{solution_name}.sln"

    # Build list of all projects
    all_projects = [csproj_path]
    if additional_projects:
        all_projects.extend(p for p in additional_projects if p.exists())

    if len(all_projects) == 1:
        # Single project - use simple format
        csproj_relative = _relative_path(solution_dir, csproj_path)
        content = _generate_solution_content(
            project_name=csproj_path.stem,
            project_path=csproj_relative,
        )
    else:
        # Multiple projects - use multi-project format
        content = _generate_multi_project_solution_content(solution_dir, all_projects)

    solution_path.write_text(content)
    return solution_path


def _collect_all_dlls(directory: Path) -> list[Path]:
    """Collect all DLLs from a directory."""
    if not directory.exists():
        return []
    return sorted(directory.glob("*.dll"), key=lambda p: p.name)


def _collect_editor_dlls(editor_managed_dir: Path) -> list[Path]:
    """Collect Unity Editor DLLs (UnityEditor*.dll) from Unity's Managed folder."""
    if not editor_managed_dir.exists():
        return []
    return sorted(editor_managed_dir.glob("UnityEditor*.dll"), key=lambda p: p.name)


def _collect_package_dlls(packages_dir: Path) -> list[Path]:
    """Collect DLLs from NuGet packages in Assets/Packages folder.

    Packages have a nested structure like:
    Packages/sqlite-net-pcl.1.9.172/lib/netstandard2.0/SQLite-net.dll
    """
    if not packages_dir.exists():
        return []

    # Find DLLs in the netstandard2.0 subdirectories
    dlls = list(packages_dir.glob("*/lib/netstandard2.0/*.dll"))
    return sorted(dlls, key=lambda p: p.name)


def _dedupe_dlls_by_name(dlls: list[Path]) -> list[Path]:
    """Remove duplicate DLLs by filename, preserving first occurrence."""
    seen: set[str] = set()
    result: list[Path] = []
    for dll in dlls:
        if dll.name not in seen:
            seen.add(dll.name)
            result.append(dll)
    return result


def _parse_csproj_references(csproj_path: Path) -> list[Path]:
    """Parse a .csproj file and extract all DLL reference paths.

    Reads the XML of a csproj file and extracts the absolute paths of all
    <Reference> elements that have a <HintPath> child.

    Args:
        csproj_path: Path to the .csproj file to parse.

    Returns:
        List of absolute paths to referenced DLLs.
    """
    if not csproj_path.exists():
        return []

    try:
        tree = ET.parse(csproj_path)
        root = tree.getroot()
    except ET.ParseError:
        return []

    # Handle both namespaced and non-namespaced csproj formats
    # SDK-style csproj files typically don't have a namespace
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}")[0] + "}"

    dll_paths: list[Path] = []
    csproj_dir = csproj_path.parent

    # Find all Reference elements with HintPath children
    for reference in root.iter(f"{namespace}Reference"):
        hint_path_elem = reference.find(f"{namespace}HintPath")
        if hint_path_elem is not None and hint_path_elem.text:
            # Convert relative path to absolute
            relative_path = Path(hint_path_elem.text)
            absolute_path = (csproj_dir / relative_path).resolve()
            if absolute_path.exists():
                dll_paths.append(absolute_path)

    return sorted(dll_paths, key=lambda p: p.name)


def _relative_path(from_dir: Path, to_path: Path) -> Path:
    """Calculate relative path from one directory to another path."""
    try:
        return to_path.relative_to(from_dir)
    except ValueError:
        # Paths don't share a common base, calculate manually
        from_parts = from_dir.resolve().parts
        to_parts = to_path.resolve().parts

        # Find common prefix length
        common_length = 0
        for i, (a, b) in enumerate(zip(from_parts, to_parts, strict=False)):
            if a != b:
                break
            common_length = i + 1

        # Build relative path
        up_count = len(from_parts) - common_length
        relative_parts = [".."] * up_count + list(to_parts[common_length:])
        return Path(*relative_parts) if relative_parts else Path()


def _generate_csproj_content(
    managed_dlls: list[Path],
    plugin_dlls: list[Path],
    managed_relative: Path,
    plugins_relative: Path,
) -> str:
    """Generate the .csproj XML content for game scripts."""
    warnings = ";".join(SUPPRESSED_WARNINGS)

    references = []

    # Add managed DLL references
    for dll in managed_dlls:
        hint_path = managed_relative / dll.name
        references.append(
            f'    <Reference Include="{dll.stem}">\n'
            f"      <HintPath>{hint_path}</HintPath>\n"
            f"      <Private>false</Private>\n"
            f"    </Reference>"
        )

    # Add plugin DLL references
    for dll in plugin_dlls:
        hint_path = plugins_relative / dll.name
        references.append(
            f'    <Reference Include="{dll.stem}">\n'
            f"      <HintPath>{hint_path}</HintPath>\n"
            f"      <Private>false</Private>\n"
            f"    </Reference>"
        )

    references_xml = "\n".join(references)

    return f"""<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFramework>netstandard2.1</TargetFramework>
    <LangVersion>9.0</LangVersion>
    <Nullable>disable</Nullable>
    <ImplicitUsings>disable</ImplicitUsings>
    <AllowUnsafeBlocks>true</AllowUnsafeBlocks>

    <!-- Disable implicit framework references to avoid conflicts with Unity's mscorlib -->
    <DisableImplicitFrameworkReferences>true</DisableImplicitFrameworkReferences>

    <!-- LSP-only project - disable build artifacts -->
    <ProduceReferenceAssembly>false</ProduceReferenceAssembly>
    <GenerateDocumentationFile>false</GenerateDocumentationFile>
    <GenerateAssemblyInfo>false</GenerateAssemblyInfo>
    <EnableDefaultCompileItems>true</EnableDefaultCompileItems>

    <!-- Suppress warnings from decompiled code -->
    <NoWarn>{warnings}</NoWarn>
  </PropertyGroup>

  <ItemGroup>
{references_xml}
  </ItemGroup>

</Project>
"""


def _generate_editor_csproj_content_from_paths(
    csproj_dir: Path,
    dll_paths: list[Path],
    game_scripts_relative: Path,
) -> str:
    """Generate the .csproj XML content for Editor scripts from absolute DLL paths.

    Args:
        csproj_dir: Directory where the csproj will be written.
        dll_paths: List of absolute paths to DLLs.
        game_scripts_relative: Relative path to game scripts csproj.
    """
    references = []

    for dll in dll_paths:
        hint_path = _relative_path(csproj_dir, dll)
        references.append(
            f'    <Reference Include="{dll.stem}">\n'
            f"      <HintPath>{hint_path}</HintPath>\n"
            f"      <Private>false</Private>\n"
            f"    </Reference>"
        )

    references_xml = "\n".join(references)

    return f"""<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFramework>netstandard2.1</TargetFramework>
    <LangVersion>9.0</LangVersion>
    <Nullable>disable</Nullable>
    <ImplicitUsings>disable</ImplicitUsings>
    <AllowUnsafeBlocks>true</AllowUnsafeBlocks>

    <!-- Disable implicit framework references to avoid conflicts with Unity's mscorlib -->
    <DisableImplicitFrameworkReferences>true</DisableImplicitFrameworkReferences>

    <!-- LSP-only project - disable build artifacts -->
    <ProduceReferenceAssembly>false</ProduceReferenceAssembly>
    <GenerateDocumentationFile>false</GenerateDocumentationFile>
    <GenerateAssemblyInfo>false</GenerateAssemblyInfo>
    <EnableDefaultCompileItems>true</EnableDefaultCompileItems>
  </PropertyGroup>

  <ItemGroup>
{references_xml}
  </ItemGroup>

  <ItemGroup>
    <ProjectReference Include="{game_scripts_relative}" />
  </ItemGroup>

</Project>
"""


def _generate_solution_content(project_name: str, project_path: Path) -> str:
    """Generate the .sln file content for a single project."""
    # Generate deterministic GUIDs based on project name
    project_guid = str(uuid.uuid5(uuid.NAMESPACE_DNS, project_name)).upper()
    solution_guid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{project_name}-solution")).upper()

    # Standard GUID for C# project type
    csharp_project_type = "FAE04EC0-301F-11D3-BF4B-00C04F79EFBC"

    # Convert path separators to Windows style for .sln compatibility
    project_path_str = str(project_path).replace("/", "\\")

    return f"""Microsoft Visual Studio Solution File, Format Version 12.00
# Visual Studio Version 17
VisualStudioVersion = 17.0.31903.59
MinimumVisualStudioVersion = 10.0.40219.1
Project("{{{csharp_project_type}}}") = "{project_name}", "{project_path_str}", "{{{project_guid}}}"
EndProject
Global
\tGlobalSection(SolutionConfigurationPlatforms) = preSolution
\t\tDebug|Any CPU = Debug|Any CPU
\t\tRelease|Any CPU = Release|Any CPU
\tEndGlobalSection
\tGlobalSection(ProjectConfigurationPlatforms) = postSolution
\t\t{{{project_guid}}}.Debug|Any CPU.ActiveCfg = Debug|Any CPU
\t\t{{{project_guid}}}.Debug|Any CPU.Build.0 = Debug|Any CPU
\t\t{{{project_guid}}}.Release|Any CPU.ActiveCfg = Release|Any CPU
\t\t{{{project_guid}}}.Release|Any CPU.Build.0 = Release|Any CPU
\tEndGlobalSection
\tGlobalSection(SolutionProperties) = preSolution
\t\tHideSolutionNode = FALSE
\tEndGlobalSection
\tGlobalSection(ExtensibilityGlobals) = postSolution
\t\tSolutionGuid = {{{solution_guid}}}
\tEndGlobalSection
EndGlobal
"""


def _generate_multi_project_solution_content(solution_dir: Path, projects: list[Path]) -> str:
    """Generate the .sln file content for multiple projects."""
    csharp_project_type = "FAE04EC0-301F-11D3-BF4B-00C04F79EFBC"
    solution_guid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "multi-project-solution")).upper()

    project_declarations = []
    config_lines = []

    for csproj in projects:
        project_name = csproj.stem
        project_guid = str(uuid.uuid5(uuid.NAMESPACE_DNS, project_name)).upper()
        rel_path = _relative_path(solution_dir, csproj)
        path_str = str(rel_path).replace("/", "\\")

        project_declarations.append(
            f'Project("{{{csharp_project_type}}}") = "{project_name}", "{path_str}", "{{{project_guid}}}"\nEndProject'
        )

        config_lines.extend(
            [
                f"\t\t{{{project_guid}}}.Debug|Any CPU.ActiveCfg = Debug|Any CPU",
                f"\t\t{{{project_guid}}}.Debug|Any CPU.Build.0 = Debug|Any CPU",
                f"\t\t{{{project_guid}}}.Release|Any CPU.ActiveCfg = Release|Any CPU",
                f"\t\t{{{project_guid}}}.Release|Any CPU.Build.0 = Release|Any CPU",
            ]
        )

    projects_section = "\n".join(project_declarations)
    configs_section = "\n".join(config_lines)

    return f"""Microsoft Visual Studio Solution File, Format Version 12.00
# Visual Studio Version 17
VisualStudioVersion = 17.0.31903.59
MinimumVisualStudioVersion = 10.0.40219.1
{projects_section}
Global
\tGlobalSection(SolutionConfigurationPlatforms) = preSolution
\t\tDebug|Any CPU = Debug|Any CPU
\t\tRelease|Any CPU = Release|Any CPU
\tEndGlobalSection
\tGlobalSection(ProjectConfigurationPlatforms) = postSolution
{configs_section}
\tEndGlobalSection
\tGlobalSection(SolutionProperties) = preSolution
\t\tHideSolutionNode = FALSE
\tEndGlobalSection
\tGlobalSection(ExtensibilityGlobals) = postSolution
\t\tSolutionGuid = {{{solution_guid}}}
\tEndGlobalSection
EndGlobal
"""


# Standard GUIDs for solution folder and C# project types
_SOLUTION_FOLDER_TYPE = "2150E333-8FDC-42A3-9474-1A3956D46DE8"
_CSHARP_PROJECT_TYPE = "FAE04EC0-301F-11D3-BF4B-00C04F79EFBC"


@dataclass
class ProjectEntry:
    """A project entry for inclusion in a solution file."""

    name: str
    path: Path
    folder: str | None = None  # Solution folder to place project in


def discover_mod_projects(mods_dir: Path) -> tuple[list[Path], list[Path]]:
    """Discover mod and test projects under the mods directory.

    Scans for .csproj files, categorizing them as either main mod projects
    or test projects based on path and naming conventions.

    Args:
        mods_dir: Path to the mods directory (e.g., src/mods/).

    Returns:
        Tuple of (mod_projects, test_projects) as lists of paths to .csproj files.
    """
    if not mods_dir.exists():
        return [], []

    mod_projects: list[Path] = []
    test_projects: list[Path] = []

    for csproj in mods_dir.rglob("*.csproj"):
        # Skip build artifacts
        if "obj" in csproj.parts or "bin" in csproj.parts:
            continue

        # Categorize as test or main project
        if "tests" in csproj.parts or csproj.stem.endswith(".Tests"):
            test_projects.append(csproj)
        else:
            mod_projects.append(csproj)

    return sorted(mod_projects), sorted(test_projects)


def generate_root_solution(
    solution_path: Path,
    game_script_projects: dict[str, Path],
    mod_projects: list[Path],
    test_projects: list[Path],
) -> Path:
    """Generate a root solution file including all projects.

    Creates an Erenshor.sln at the specified path that includes game script
    projects for each variant, mod projects, and test projects, organized
    into solution folders.

    Args:
        solution_path: Path where the .sln file will be created.
        game_script_projects: Dict mapping variant name to .csproj path.
        mod_projects: List of mod .csproj paths.
        test_projects: List of test .csproj paths.

    Returns:
        Path to the generated .sln file.

    Raises:
        ValueError: If no projects are provided.
    """
    if not game_script_projects and not mod_projects and not test_projects:
        msg = "No projects provided for solution generation"
        raise ValueError(msg)

    # Build list of all projects with their solution folders
    projects: list[ProjectEntry] = []

    # Add game script projects under "GameScripts" folder
    for variant, csproj_path in sorted(game_script_projects.items()):
        projects.append(
            ProjectEntry(
                name=f"Assembly-CSharp ({variant})",
                path=csproj_path,
                folder="GameScripts",
            )
        )

    # Add mod projects under "Mods" folder
    for csproj_path in mod_projects:
        projects.append(
            ProjectEntry(
                name=csproj_path.stem,
                path=csproj_path,
                folder="Mods",
            )
        )

    # Add test projects under "Tests" folder
    for csproj_path in test_projects:
        projects.append(
            ProjectEntry(
                name=csproj_path.stem,
                path=csproj_path,
                folder="Tests",
            )
        )

    content = _generate_root_solution_content(solution_path.parent, projects)
    solution_path.write_text(content)
    return solution_path


def _generate_project_guid(name: str) -> str:
    """Generate a deterministic GUID for a project."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"erenshor-{name}")).upper()


def _generate_root_solution_content(
    solution_dir: Path,
    projects: list[ProjectEntry],
) -> str:
    """Generate the .sln file content for multiple projects with folders."""
    solution_guid = _generate_project_guid("erenshor-root-solution")

    # Collect unique folder names and generate GUIDs for them
    folders: dict[str, str] = {}
    for project in projects:
        if project.folder and project.folder not in folders:
            folders[project.folder] = _generate_project_guid(f"folder-{project.folder}")

    # Build project declarations
    project_declarations: list[str] = []

    # Add solution folders first
    for folder_name, folder_guid in sorted(folders.items()):
        project_declarations.append(
            f'Project("{{{_SOLUTION_FOLDER_TYPE}}}") = "{folder_name}", '
            f'"{folder_name}", "{{{folder_guid}}}"\n'
            f"EndProject"
        )

    # Add actual projects
    project_guids: dict[str, str] = {}
    for project in projects:
        project_guid = _generate_project_guid(project.name)
        project_guids[project.name] = project_guid

        # Calculate relative path from solution directory
        rel_path = _relative_path(solution_dir, project.path)
        path_str = str(rel_path).replace("/", "\\")

        project_declarations.append(
            f'Project("{{{_CSHARP_PROJECT_TYPE}}}") = "{project.name}", "{path_str}", "{{{project_guid}}}"\nEndProject'
        )

    # Build configuration mappings
    config_lines: list[str] = []
    for project in projects:
        guid = project_guids[project.name]
        config_lines.extend(
            [
                f"\t\t{{{guid}}}.Debug|Any CPU.ActiveCfg = Debug|Any CPU",
                f"\t\t{{{guid}}}.Debug|Any CPU.Build.0 = Debug|Any CPU",
                f"\t\t{{{guid}}}.Release|Any CPU.ActiveCfg = Release|Any CPU",
                f"\t\t{{{guid}}}.Release|Any CPU.Build.0 = Release|Any CPU",
            ]
        )

    # Build nested projects section (assigns projects to folders)
    nested_lines: list[str] = []
    for project in projects:
        if project.folder:
            project_guid = project_guids[project.name]
            folder_guid = folders[project.folder]
            nested_lines.append(f"\t\t{{{project_guid}}} = {{{folder_guid}}}")

    # Assemble the solution file
    projects_section = "\n".join(project_declarations)
    configs_section = "\n".join(config_lines)
    nested_section = "\n".join(nested_lines)

    nested_global = ""
    if nested_lines:
        nested_global = f"""
\tGlobalSection(NestedProjects) = preSolution
{nested_section}
\tEndGlobalSection"""

    return f"""Microsoft Visual Studio Solution File, Format Version 12.00
# Visual Studio Version 17
VisualStudioVersion = 17.0.31903.59
MinimumVisualStudioVersion = 10.0.40219.1
{projects_section}
Global
\tGlobalSection(SolutionConfigurationPlatforms) = preSolution
\t\tDebug|Any CPU = Debug|Any CPU
\t\tRelease|Any CPU = Release|Any CPU
\tEndGlobalSection
\tGlobalSection(ProjectConfigurationPlatforms) = postSolution
{configs_section}
\tEndGlobalSection
\tGlobalSection(SolutionProperties) = preSolution
\t\tHideSolutionNode = FALSE
\tEndGlobalSection{nested_global}
\tGlobalSection(ExtensibilityGlobals) = postSolution
\t\tSolutionGuid = {{{solution_guid}}}
\tEndGlobalSection
EndGlobal
"""
