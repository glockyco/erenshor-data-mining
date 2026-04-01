using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Position;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class ZoneAccessResolverTests
{
    [Fact]
    public void LockedTravelZone_UsesZoneLineQuestBlocker()
    {
        var graph = new TestGraphBuilder()
            .AddZone("zone:a", "Zone A", scene: "ZoneA")
            .AddZone("zone:b", "Zone B", scene: "ZoneB")
            .AddZoneLine("zl:ab", "ZL A→B", scene: "ZoneA", destinationZoneKey: "zone:b",
                x: 10, y: 0, z: 5)
            .AddQuest("quest:gate", "Gate Quest", dbName: "GateQuest")
            .AddEdge("quest:gate", "zl:ab", EdgeType.UnlocksZoneLine)
            .Build();

        var snapshot = new StateSnapshot { CurrentZone = "ZoneA" };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var resolver = new ZoneAccessResolver(harness.Graph, harness.Tracker, harness.Unlocks, harness.Router);

        var blocked = resolver.FindBlockedRoute("ZoneB");

        Assert.NotNull(blocked);
        Assert.Equal("zl:ab", blocked!.ZoneLineNode.Key);
        Assert.Contains(blocked.Evaluation.BlockingSources, n => n.Key == "quest:gate");
    }

    [Fact]
    public void ReachableZone_ReturnsNoBlockedRoute()
    {
        var graph = new TestGraphBuilder()
            .AddZone("zone:a", "Zone A", scene: "ZoneA")
            .AddZone("zone:b", "Zone B", scene: "ZoneB")
            .AddZoneLine("zl:ab", "ZL A→B", scene: "ZoneA", destinationZoneKey: "zone:b",
                x: 10, y: 0, z: 5)
            .Build();

        var snapshot = new StateSnapshot { CurrentZone = "ZoneA" };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var resolver = new ZoneAccessResolver(harness.Graph, harness.Tracker, harness.Unlocks, harness.Router);

        Assert.Null(resolver.FindBlockedRoute("ZoneB"));
    }

    [Fact]
    public void LockedRoutePrefersFirstBlockedHopOnPath()
    {
        var graph = new TestGraphBuilder()
            .AddZone("zone:a", "Zone A", scene: "ZoneA")
            .AddZone("zone:b", "Zone B", scene: "ZoneB")
            .AddZone("zone:c", "Zone C", scene: "ZoneC")
            .AddZoneLine("zl:ab", "ZL A→B", scene: "ZoneA", destinationZoneKey: "zone:b",
                x: 10, y: 0, z: 5)
            .AddZoneLine("zl:bc", "ZL B→C", scene: "ZoneB", destinationZoneKey: "zone:c",
                x: 20, y: 0, z: 5)
            .AddQuest("quest:first", "First Gate", dbName: "FirstGate")
            .AddQuest("quest:second", "Second Gate", dbName: "SecondGate")
            .AddEdge("quest:first", "zl:ab", EdgeType.UnlocksZoneLine)
            .AddEdge("quest:second", "zl:bc", EdgeType.UnlocksZoneLine)
            .Build();

        var snapshot = new StateSnapshot { CurrentZone = "ZoneA" };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var resolver = new ZoneAccessResolver(harness.Graph, harness.Tracker, harness.Unlocks, harness.Router);

        var blocked = resolver.FindBlockedRoute("ZoneC");

        Assert.NotNull(blocked);
        Assert.Equal("zl:ab", blocked!.ZoneLineNode.Key);
        Assert.Contains(blocked.Evaluation.BlockingSources, n => n.Key == "quest:first");
        Assert.DoesNotContain(blocked.Evaluation.BlockingSources, n => n.Key == "quest:second");
    }
}
