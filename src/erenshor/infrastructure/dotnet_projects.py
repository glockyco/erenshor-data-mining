"""Canonical maintained .NET restore targets."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DotnetRestoreTarget:
    """One maintained project dependency graph."""

    project: str
    lock_file: str | None
    properties: tuple[tuple[str, str], ...] = ()


_PRODUCTION_MODS = (
    "AdventureGuide",
    "InteractiveMapCompanion",
    "JusticeForF7",
    "MapTileCapture",
    "Sprint",
)

MAINTAINED_DOTNET_RESTORE_TARGETS = (
    *(
        DotnetRestoreTarget(
            project=f"src/mods/{mod}/{mod}.csproj",
            lock_file=f"src/mods/{mod}/packages.{loader}.lock.json",
            properties=(("ModLoader", loader),),
        )
        for mod in _PRODUCTION_MODS
        for loader in ("bepinex", "lunaris")
    ),
    DotnetRestoreTarget(
        project="src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj",
        lock_file="src/mods/AdventureGuide/tests/AdventureGuide.Tests/packages.lock.json",
    ),
    DotnetRestoreTarget(
        project=(
            "src/mods/InteractiveMapCompanion/tests/InteractiveMapCompanion.Tests/InteractiveMapCompanion.Tests.csproj"
        ),
        lock_file=("src/mods/InteractiveMapCompanion/tests/InteractiveMapCompanion.Tests/packages.lock.json"),
    ),
    DotnetRestoreTarget(
        project="src/mods/JusticeForF7/tests/JusticeForF7.Tests/JusticeForF7.Tests.csproj",
        lock_file="src/mods/JusticeForF7/tests/JusticeForF7.Tests/packages.lock.json",
    ),
    DotnetRestoreTarget(
        project="src/mods/Sprint/tests/Sprint.Tests/Sprint.Tests.csproj",
        lock_file="src/mods/Sprint/tests/Sprint.Tests/packages.lock.json",
    ),
    DotnetRestoreTarget(
        project="src/mods/tests/LoaderAdapter.Tests/LoaderAdapter.Tests.csproj",
        lock_file="src/mods/tests/LoaderAdapter.Tests/packages.lock.json",
    ),
    DotnetRestoreTarget(
        project="src/tools/CodeFacts/CodeFacts.csproj",
        lock_file="src/tools/CodeFacts/packages.lock.json",
    ),
    DotnetRestoreTarget(
        project="src/tools/CodeFacts/tests/CodeFacts.Tests/CodeFacts.Tests.csproj",
        lock_file="src/tools/CodeFacts/tests/CodeFacts.Tests/packages.lock.json",
    ),
    DotnetRestoreTarget(
        project="src/tools/CodeFacts/tests/FixtureLib/FixtureLib.csproj",
        lock_file=None,
    ),
    DotnetRestoreTarget(
        project="src/tools/ExportSurface/ExportSurface.csproj",
        lock_file="src/tools/ExportSurface/packages.lock.json",
    ),
    DotnetRestoreTarget(
        project="src/tools/ExportSurface/tests/ExportSurface.Tests/ExportSurface.Tests.csproj",
        lock_file="src/tools/ExportSurface/tests/ExportSurface.Tests/packages.lock.json",
    ),
)
