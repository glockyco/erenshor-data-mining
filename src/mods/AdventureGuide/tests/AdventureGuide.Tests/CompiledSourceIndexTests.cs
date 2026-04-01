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
}
