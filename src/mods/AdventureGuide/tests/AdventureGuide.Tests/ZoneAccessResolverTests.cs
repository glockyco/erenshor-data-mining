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
        var builder = new CompiledGuideBuilder()
            .AddZone("zone:a", scene: "ZoneA")
            .AddZone("zone:b", scene: "ZoneB")
            .AddZoneLine("zl:ab", scene: "ZoneA", destinationZoneKey: "zone:b", x: 10, y: 0, z: 5)
            .AddQuest("quest:gate", dbName: "GateQuest")
            .AddEdge("quest:gate", "zl:ab", EdgeType.UnlocksZoneLine);

        var snapshot = new StateSnapshot { CurrentZone = "ZoneA" };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var resolver = new ZoneAccessResolver(
            harness.Guide,
            harness.Tracker,
            harness.Unlocks,
            harness.Router
        );

        var blocked = resolver.FindBlockedRoute("ZoneB");

        Assert.NotNull(blocked);
        Assert.Equal("zl:ab", blocked!.ZoneLineNode.Key);
        Assert.Contains(blocked.Evaluation.BlockingSources, n => n.Key == "quest:gate");
    }

    [Fact]
    public void ReachableZone_ReturnsNoBlockedRoute()
    {
        var builder = new CompiledGuideBuilder()
            .AddZone("zone:a", scene: "ZoneA")
            .AddZone("zone:b", scene: "ZoneB")
            .AddZoneLine("zl:ab", scene: "ZoneA", destinationZoneKey: "zone:b", x: 10, y: 0, z: 5);

        var snapshot = new StateSnapshot { CurrentZone = "ZoneA" };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var resolver = new ZoneAccessResolver(
            harness.Guide,
            harness.Tracker,
            harness.Unlocks,
            harness.Router
        );

        Assert.Null(resolver.FindBlockedRoute("ZoneB"));
    }

    [Fact]
    public void LockedRoutePrefersFirstBlockedHopOnPath()
    {
        var builder = new CompiledGuideBuilder()
            .AddZone("zone:a", scene: "ZoneA")
            .AddZone("zone:b", scene: "ZoneB")
            .AddZone("zone:c", scene: "ZoneC")
            .AddZoneLine("zl:ab", scene: "ZoneA", destinationZoneKey: "zone:b", x: 10, y: 0, z: 5)
            .AddZoneLine("zl:bc", scene: "ZoneB", destinationZoneKey: "zone:c", x: 20, y: 0, z: 5)
            .AddQuest("quest:first", dbName: "FirstGate")
            .AddQuest("quest:second", dbName: "SecondGate")
            .AddEdge("quest:first", "zl:ab", EdgeType.UnlocksZoneLine)
            .AddEdge("quest:second", "zl:bc", EdgeType.UnlocksZoneLine);

        var snapshot = new StateSnapshot { CurrentZone = "ZoneA" };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var resolver = new ZoneAccessResolver(
            harness.Guide,
            harness.Tracker,
            harness.Unlocks,
            harness.Router
        );

        var blocked = resolver.FindBlockedRoute("ZoneC");

        Assert.NotNull(blocked);
        Assert.Equal("zl:ab", blocked!.ZoneLineNode.Key);
        Assert.Contains(blocked.Evaluation.BlockingSources, n => n.Key == "quest:first");
        Assert.DoesNotContain(blocked.Evaluation.BlockingSources, n => n.Key == "quest:second");
    }
}
