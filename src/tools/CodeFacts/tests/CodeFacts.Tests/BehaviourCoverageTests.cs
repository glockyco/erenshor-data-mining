using ICSharpCode.Decompiler;
using ICSharpCode.Decompiler.CSharp;
using ICSharpCode.Decompiler.Metadata;
using Xunit;

namespace CodeFacts.Tests;

public sealed class BehaviourCoverageTests
{
    private static readonly string AssemblyPath = typeof(BehaviourFixtures.AllApis)
        .Assembly
        .Location;

    private static (
        SortedDictionary<string, SortedSet<string>> Inventory,
        HashSet<string> Types
    ) Scan()
    {
        var resolver = new UniversalAssemblyResolver(
            AssemblyPath,
            throwOnError: false,
            targetFramework: null
        );
        var decompiler = new CSharpDecompiler(AssemblyPath, resolver, new DecompilerSettings());
        return (
            BehaviourCoverage.Inventory(decompiler),
            decompiler
                .TypeSystem.MainModule.TypeDefinitions.Select(t => t.FullName)
                .ToHashSet(StringComparer.Ordinal)
        );
    }

    private static BehaviourCatalog Catalog(
        IReadOnlyDictionary<string, SortedSet<string>> inventory
    ) =>
        new(
            1,
            inventory.ToDictionary(
                pair => pair.Key,
                pair => new BehaviourEntry("core", pair.Value.ToList(), Component: "fixture")
            )
        );

    [Fact]
    public void Inventory_resolves_all_apis_and_ignores_unrelated_names_and_wrong_directions()
    {
        var (inventory, _) = Scan();
        Assert.Equal(
            new[]
            {
                "AtmosphereColors.SinceRain",
                "AtmosphereColors.WeightGoal",
                "AtmosphereColors.isRaining",
                "Character.Invulnerable",
                "GameData.AccountClaimedReliquary",
                "GameData.AssignQuest",
                "GameData.CompletedQuests",
                "GameData.FinishQuest",
                "GameData.HasQuest",
                "GameData.IsQuestDone",
                "GlobalFactionManager.ModifyFaction",
                "Inventory.HasCosmetic",
                "Inventory.HasItem",
                "NPCFaction.Value",
                "SceneChange.ChangeScene",
                "SceneChange.ChangeSceneSafe",
                "SpawnPoint.MyNPCAlive",
                "WorldFaction.FactionValue",
            },
            inventory["BehaviourFixtures.AllApis"]
        );
        Assert.DoesNotContain("BehaviourFixtures.WrongDirection", inventory.Keys);
        Assert.DoesNotContain("BehaviourFixtures.Unrelated", inventory.Keys);
        Assert.DoesNotContain("BehaviourFixtures.Outer", inventory.Keys);
        Assert.DoesNotContain("GameData", inventory.Keys);
        Assert.DoesNotContain("AtmosphereColors", inventory.Keys);
        Assert.DoesNotContain("SpawnPoint", inventory.Keys);
        Assert.DoesNotContain("WorldFaction", inventory.Keys);
        Assert.DoesNotContain("NPCFaction", inventory.Keys);
        Assert.Contains(
            inventory,
            pair =>
                pair.Key.EndsWith("Nested", StringComparison.Ordinal)
                && pair.Value.SetEquals(["GameData.IsQuestDone"])
        );
    }

    [Fact]
    public void Complete_catalog_passes()
    {
        var (inventory, types) = Scan();
        Assert.Empty(BehaviourCoverage.Check(inventory, Catalog(inventory), types));
    }

    [Fact]
    public void Missing_entry_names_type_and_apis()
    {
        var (inventory, types) = Scan();
        var catalog = Catalog(inventory);
        catalog.Types.Remove("BehaviourFixtures.AllApis");
        string error = Assert.Single(BehaviourCoverage.Check(inventory, catalog, types));
        Assert.Contains("BehaviourFixtures.AllApis", error);
        Assert.Contains("GameData.IsQuestDone", error);
    }

    [Theory]
    [InlineData("absent from assembly", "MissingType")]
    [InlineData("no listed progression API use", "BehaviourFixtures.Unrelated")]
    public void Stale_entry_names_cause(string cause, string type)
    {
        var (inventory, types) = Scan();
        var catalog = Catalog(inventory);
        catalog.Types[type] = new("excluded", [], Reason: "fixture");
        string error = Assert.Single(BehaviourCoverage.Check(inventory, catalog, types));
        Assert.Contains(type, error);
        Assert.Contains(cause, error);
    }

    [Fact]
    public void Changed_api_set_fails()
    {
        var (inventory, types) = Scan();
        var catalog = Catalog(inventory);
        catalog.Types["BehaviourFixtures.AllApis"].Apis.Remove("Inventory.HasItem");
        Assert.Contains(
            "BehaviourFixtures.AllApis: changed API set",
            Assert.Single(BehaviourCoverage.Check(inventory, catalog, types))
        );
    }

    [Theory]
    [InlineData("pending")]
    [InlineData("adapter")]
    [InlineData("core")]
    [InlineData("excluded")]
    [InlineData("unknown")]
    public void Incomplete_classification_fails(string classification)
    {
        var (inventory, types) = Scan();
        var catalog = Catalog(inventory);
        catalog.Types["BehaviourFixtures.AllApis"] = new(
            classification,
            inventory["BehaviourFixtures.AllApis"].ToList()
        );
        Assert.Contains(
            "BehaviourFixtures.AllApis",
            Assert.Single(BehaviourCoverage.Check(inventory, catalog, types))
        );
    }

    [Fact]
    public void Pending_with_task_passes()
    {
        var (inventory, types) = Scan();
        var catalog = Catalog(inventory);
        catalog.Types["BehaviourFixtures.AllApis"] = new(
            "pending",
            inventory["BehaviourFixtures.AllApis"].ToList(),
            Tasks: ["3.2"]
        );
        Assert.Empty(BehaviourCoverage.Check(inventory, catalog, types));
    }
}
