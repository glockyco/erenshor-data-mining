using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

/// <summary>
/// Tests for <see cref="State.UnlockEvaluator"/> (grouped/ungrouped unlock
/// edge evaluation) and <see cref="Position.ZoneRouter"/> (BFS routing over
/// zone line adjacency with lock-awareness).
/// </summary>
public class UnlockEvaluationTests
{
    // -- UnlockEvaluator ---------------------------------------------------------

    [Fact]
    public void UnconditionalUnlockSatisfied()
    {
        var builder = new CompiledGuideBuilder()
            .AddZoneLine("zl:a", scene: "ZoneA", destinationZoneKey: "zone:b", x: 1, y: 0, z: 0)
            .AddQuest("quest:q", dbName: "QuestQ")
            .AddEdge("quest:q", "zl:a", EdgeType.UnlocksZoneLine);

        var snapshot = new StateSnapshot { CompletedQuests = new List<string> { "QuestQ" } };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);

        var node = harness.Guide.GetNode("zl:a")!;
        var eval = harness.Unlocks.Evaluate(node);

        Assert.True(eval.IsUnlocked);
    }

    [Fact]
    public void UnconditionalUnlockBlocked()
    {
        var builder = new CompiledGuideBuilder()
            .AddZoneLine("zl:a", scene: "ZoneA", destinationZoneKey: "zone:b", x: 1, y: 0, z: 0)
            .AddQuest("quest:q", dbName: "QuestQ")
            .AddEdge("quest:q", "zl:a", EdgeType.UnlocksZoneLine);

        var harness = SnapshotHarness.FromBuilder(builder);

        var node = harness.Guide.GetNode("zl:a")!;
        var eval = harness.Unlocks.Evaluate(node);

        Assert.False(eval.IsUnlocked);
        Assert.Contains(eval.BlockingSources, s => s.Key == "quest:q");
    }

    [Fact]
    public void GroupedAND_PartiallyComplete_Blocked()
    {
        var builder = new CompiledGuideBuilder()
            .AddZoneLine("zl:a", scene: "ZoneA", destinationZoneKey: "zone:b", x: 1, y: 0, z: 0)
            .AddQuest("quest:a", dbName: "QuestA")
            .AddQuest("quest:b", dbName: "QuestB")
            .AddEdge("quest:a", "zl:a", EdgeType.UnlocksZoneLine, group: "g1")
            .AddEdge("quest:b", "zl:a", EdgeType.UnlocksZoneLine, group: "g1");

        // Only quest:a completed -- both required within group (AND).
        var snapshot = new StateSnapshot { CompletedQuests = new List<string> { "QuestA" } };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);

        var node = harness.Guide.GetNode("zl:a")!;
        var eval = harness.Unlocks.Evaluate(node);

        Assert.False(eval.IsUnlocked);
    }

    [Fact]
    public void GroupedOR_OneGroupSatisfied_Unlocked()
    {
        var builder = new CompiledGuideBuilder()
            .AddZoneLine("zl:a", scene: "ZoneA", destinationZoneKey: "zone:b", x: 1, y: 0, z: 0)
            .AddQuest("quest:a", dbName: "QuestA")
            .AddQuest("quest:b", dbName: "QuestB")
            .AddEdge("quest:a", "zl:a", EdgeType.UnlocksZoneLine, group: "g1")
            .AddEdge("quest:b", "zl:a", EdgeType.UnlocksZoneLine, group: "g2");

        // Only quest:b completed -- group g2 satisfied -> OR passes.
        var snapshot = new StateSnapshot { CompletedQuests = new List<string> { "QuestB" } };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);

        var node = harness.Guide.GetNode("zl:a")!;
        var eval = harness.Unlocks.Evaluate(node);

        Assert.True(eval.IsUnlocked);
    }

    [Fact]
    public void ItemKeyringSource_Unlocked()
    {
        var builder = new CompiledGuideBuilder()
            .AddDoor("door:d", scene: "ZoneA")
            .AddItem("item:key")
            .AddEdge("item:key", "door:d", EdgeType.UnlocksDoor);

        var snapshot = new StateSnapshot { Keyring = new List<string> { "item:key" } };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);

        var node = harness.Guide.GetNode("door:d")!;
        var eval = harness.Unlocks.Evaluate(node);

        Assert.True(eval.IsUnlocked);
    }

    [Fact]
    public void ItemKeyringSource_NotPossessed_Blocked()
    {
        var builder = new CompiledGuideBuilder()
            .AddDoor("door:d", scene: "ZoneA")
            .AddItem("item:key")
            .AddEdge("item:key", "door:d", EdgeType.UnlocksDoor);

        var harness = SnapshotHarness.FromBuilder(builder);

        var node = harness.Guide.GetNode("door:d")!;
        var eval = harness.Unlocks.Evaluate(node);

        Assert.False(eval.IsUnlocked);
        Assert.Contains(eval.BlockingSources, s => s.Key == "item:key");
    }

    [Fact]
    public void CharacterUnlockByQuest_Blocked()
    {
        var builder = new CompiledGuideBuilder()
            .AddCharacter("character:c", scene: "ZoneA")
            .AddQuest("quest:q", dbName: "QuestQ")
            .AddEdge("quest:q", "character:c", EdgeType.UnlocksCharacter);

        var harness = SnapshotHarness.FromBuilder(builder);

        var node = harness.Guide.GetNode("character:c")!;
        var eval = harness.Unlocks.Evaluate(node);

        Assert.False(eval.IsUnlocked);
        Assert.Contains(eval.BlockingSources, s => s.Key == "quest:q");
    }

    // -- ZoneRouter --------------------------------------------------------------

    [Fact]
    public void DirectRoute_TwoZones()
    {
        // Zone A --[zl:ab]--> Zone B. No unlock edges -> accessible.
        var builder = new CompiledGuideBuilder()
            .AddZone("zone:a", scene: "ZoneA")
            .AddZone("zone:b", scene: "ZoneB")
            .AddZoneLine("zl:ab", scene: "ZoneA", destinationZoneKey: "zone:b", x: 10, y: 0, z: 5);

        var harness = SnapshotHarness.FromBuilder(builder);
        var route = harness.Router.FindRoute("ZoneA", "ZoneB");

        Assert.NotNull(route);
        Assert.Equal("zone:b", route!.NextHopZoneKey);
        Assert.Equal("ZoneA", route.ZoneLineScene);
        Assert.False(route.IsLocked);
        Assert.Equal(new[] { "ZoneA", "ZoneB" }, route.Path);
    }

    [Fact]
    public void LockedHop_ReturnedWhenZoneLineLocked()
    {
        // Zone A --[zl:ab, locked]--> Zone B.
        // Lock: quest:q -> zl:ab (UnlocksZoneLine), quest:q not completed.
        var builder = new CompiledGuideBuilder()
            .AddZone("zone:a", scene: "ZoneA")
            .AddZone("zone:b", scene: "ZoneB")
            .AddZoneLine("zl:ab", scene: "ZoneA", destinationZoneKey: "zone:b", x: 10, y: 0, z: 5)
            .AddQuest("quest:q", dbName: "GateQuest")
            .AddEdge("quest:q", "zl:ab", EdgeType.UnlocksZoneLine);

        var harness = SnapshotHarness.FromBuilder(builder);

        // Accessible-only BFS fails, fallback BFS finds the locked path.
        var hops = harness.Router.FindLockedHops("ZoneA", "ZoneB");

        Assert.Single(hops);
        Assert.Equal("zl:ab", hops[0].ZoneLineKey);
        Assert.Equal("ZoneA", hops[0].FromScene);
        Assert.Equal("ZoneB", hops[0].ToScene);
    }
}
