using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace LoaderAdapter.Tests;

internal static class AdapterContractInventory
{
    internal const int ExpectedAdapterCount = 10;

    internal static IReadOnlyList<AdapterContract> Contracts { get; } =
        new[]
        {
            new AdapterContract(
                "src/mods/AdventureGuide/AdventureGuide.csproj",
                "src/mods/AdventureGuide/src/Plugin.BepInEx.cs",
                "BepInPlugin",
                "Awake",
                "_runtime",
                true
            ),
            new AdapterContract(
                "src/mods/AdventureGuide/AdventureGuide.csproj",
                "src/mods/AdventureGuide/src/Plugin.Lunaris.cs",
                "LunarisPlugin",
                "Awake",
                "_runtime",
                true
            ),
            new AdapterContract(
                "src/mods/InteractiveMapCompanion/InteractiveMapCompanion.csproj",
                "src/mods/InteractiveMapCompanion/src/Plugin.BepInEx.cs",
                "BepInPlugin",
                "Awake",
                "_runtime"
            ),
            new AdapterContract(
                "src/mods/InteractiveMapCompanion/InteractiveMapCompanion.csproj",
                "src/mods/InteractiveMapCompanion/src/Plugin.Lunaris.cs",
                "LunarisPlugin",
                "Awake",
                "_runtime"
            ),
            new AdapterContract(
                "src/mods/JusticeForF7/JusticeForF7.csproj",
                "src/mods/JusticeForF7/src/Plugin.BepInEx.cs",
                "BepInPlugin",
                "Awake",
                "_runtime"
            ),
            new AdapterContract(
                "src/mods/JusticeForF7/JusticeForF7.csproj",
                "src/mods/JusticeForF7/src/Plugin.Lunaris.cs",
                "LunarisPlugin",
                "Awake",
                "_runtime"
            ),
            new AdapterContract(
                "src/mods/MapTileCapture/MapTileCapture.csproj",
                "src/mods/MapTileCapture/src/Plugin.BepInEx.cs",
                "BepInPlugin",
                "Awake",
                "_runtime"
            ),
            new AdapterContract(
                "src/mods/MapTileCapture/MapTileCapture.csproj",
                "src/mods/MapTileCapture/src/Plugin.Lunaris.cs",
                "LunarisPlugin",
                "Awake",
                "_runtime"
            ),
            new AdapterContract(
                "src/mods/Sprint/Sprint.csproj",
                "src/mods/Sprint/src/Plugin.BepInEx.cs",
                "BepInPlugin",
                "Awake",
                "SprintRuntime"
            ),
            new AdapterContract(
                "src/mods/Sprint/Sprint.csproj",
                "src/mods/Sprint/src/Plugin.Lunaris.cs",
                "LunarisPlugin",
                "Awake",
                "SprintRuntime"
            ),
        };

    internal static string FindRepositoryRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var modsDirectory = Path.Combine(directory.FullName, "src", "mods");
            var projectMarker = Path.Combine(directory.FullName, "pyproject.toml");
            if (Directory.Exists(modsDirectory) && File.Exists(projectMarker))
                return directory.FullName;

            directory = directory.Parent;
        }

        throw new DirectoryNotFoundException(
            $"Could not locate the repository root from '{AppContext.BaseDirectory}'."
        );
    }

    internal static IReadOnlyList<string> DiscoverAdapterSources(string repositoryRoot)
    {
        var modsDirectory = Path.Combine(repositoryRoot, "src", "mods");
        return Directory
            .EnumerateFiles(modsDirectory, "Plugin.BepInEx.cs", SearchOption.AllDirectories)
            .Concat(
                Directory.EnumerateFiles(
                    modsDirectory,
                    "Plugin.Lunaris.cs",
                    SearchOption.AllDirectories
                )
            )
            .Select(path => ToRepositoryPath(repositoryRoot, path))
            .OrderBy(path => path, StringComparer.Ordinal)
            .ToArray();
    }

    private static string ToRepositoryPath(string repositoryRoot, string path) =>
        Path.GetRelativePath(repositoryRoot, path).Replace(Path.DirectorySeparatorChar, '/');
}
