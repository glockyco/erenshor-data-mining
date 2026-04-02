using AdventureGuide.Graph;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class CompiledSourceIndexTests
{
    [Fact]
    public void ItemSources_AreGroupedIntoSharedSceneSites()
    {
        var graph = new TestGraphBuilder()
            .AddItem("item:fish", "Fish")
            .AddCharacter("character:angler", "Angler")
            .AddSpawnPoint("spawn:a1", "A1", scene: "ZoneA")
            .AddSpawnPoint("spawn:a2", "A2", scene: "ZoneA")
            .AddSpawnPoint("spawn:b1", "B1", scene: "ZoneB")
            .AddEdge("character:angler", "item:fish", EdgeType.DropsItem)
            .AddEdge("character:angler", "spawn:a1", EdgeType.HasSpawn)
            .AddEdge("character:angler", "spawn:a2", EdgeType.HasSpawn)
            .AddEdge("character:angler", "spawn:b1", EdgeType.HasSpawn)
            .Build();

        graph.GetNode("spawn:a1")!.X = 1;
        graph.GetNode("spawn:a1")!.Y = 0;
        graph.GetNode("spawn:a1")!.Z = 1;
        graph.GetNode("spawn:a2")!.X = 2;
        graph.GetNode("spawn:a2")!.Y = 0;
        graph.GetNode("spawn:a2")!.Z = 2;
        graph.GetNode("spawn:b1")!.X = 3;
        graph.GetNode("spawn:b1")!.Y = 0;
        graph.GetNode("spawn:b1")!.Z = 3;

        var index = new CompiledSourceIndex(graph);
        var sites = index.GetSourceSitesForItem("item:fish");

        Assert.Equal(2, sites.Count);
        Assert.Contains(sites, s => s.SourceNodeKey == "character:angler" && s.Scene == "ZoneA" && s.StaticPositions.Count == 2);
        Assert.Contains(sites, s => s.SourceNodeKey == "character:angler" && s.Scene == "ZoneB" && s.StaticPositions.Count == 1);
    }

    [Fact]
    public void ItemSources_InSceneIndexReturnsOnlyMatchingScene()
    {
        var graph = new TestGraphBuilder()
            .AddItem("item:fish", "Fish")
            .AddCharacter("character:angler", "Angler")
            .AddSpawnPoint("spawn:a1", "A1", scene: "ZoneA")
            .AddSpawnPoint("spawn:b1", "B1", scene: "ZoneB")
            .AddEdge("character:angler", "item:fish", EdgeType.DropsItem)
            .AddEdge("character:angler", "spawn:a1", EdgeType.HasSpawn)
            .AddEdge("character:angler", "spawn:b1", EdgeType.HasSpawn)
            .Build();

        graph.GetNode("spawn:a1")!.X = 1;
        graph.GetNode("spawn:a1")!.Y = 0;
        graph.GetNode("spawn:a1")!.Z = 1;
        graph.GetNode("spawn:b1")!.X = 3;
        graph.GetNode("spawn:b1")!.Y = 0;
        graph.GetNode("spawn:b1")!.Z = 3;

        var index = new CompiledSourceIndex(graph);
        var sites = index.GetSourceSitesForItemInScene("item:fish", "ZoneA");

        var site = Assert.Single(sites);
        Assert.Equal("ZoneA", site.Scene);
        Assert.Equal("character:angler", site.SourceNodeKey);
    }

    [Fact]
    public void SourceSiteBlueprint_CraftingChain_DirectItemKey_IsIngredient()
    {
        // Ghostly Key  ←CraftedFrom←  Recipe  ←RequiresMaterial←  Iron Ore
        //                                                       ←YieldsItem←  Mineral Deposit
        //
        // Sites for item:ghostly-key must include the Mineral Deposit.
        // The site's DirectItemKey must be "item:iron-ore" (what the deposit
        // actually provides), not "item:ghostly-key" (the final crafted item).
        var graph = new TestGraphBuilder()
            .AddItem("item:ghostly-key", "Ghostly Key")
            .AddRecipe("recipe:ghostly-key", "Ghostly Key Recipe")
            .AddItem("item:iron-ore", "Iron Ore")
            .AddMiningNode("node:mineral-deposit", "Mineral Deposit", scene: "ZoneA")
            .AddEdge("item:ghostly-key",      "recipe:ghostly-key",      EdgeType.CraftedFrom)
            .AddEdge("recipe:ghostly-key",    "item:iron-ore",           EdgeType.RequiresMaterial)
            .AddEdge("node:mineral-deposit",  "item:iron-ore",           EdgeType.YieldsItem)
            .Build();

        graph.GetNode("node:mineral-deposit")!.X = 10f;
        graph.GetNode("node:mineral-deposit")!.Y = 0f;
        graph.GetNode("node:mineral-deposit")!.Z = 10f;

        var index = new CompiledSourceIndex(graph);
        var sites = index.GetSourceSitesForItem("item:ghostly-key");

        // Mineral Deposit must appear as a source of the Ghostly Key.
        var depositSite = Assert.Single(sites, s => s.SourceNodeKey == "node:mineral-deposit");

        // DirectItemKey must be the INGREDIENT (Iron Ore), not the final crafted item.
        Assert.Equal("item:iron-ore", depositSite.DirectItemKey);
        Assert.NotEqual("item:ghostly-key", depositSite.DirectItemKey);
    }

}
