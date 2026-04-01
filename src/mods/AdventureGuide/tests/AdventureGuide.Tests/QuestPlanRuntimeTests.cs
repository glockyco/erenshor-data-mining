using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class QuestPlanRuntimeTests
{
    [Fact]
    public void CompletedQuestNode_IsMarkedSatisfied()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .Build();

        var snapshot = new StateSnapshot { CompletedQuests = ["QuestQ"] };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var plan = new QuestPlanBuilder(graph, harness.GameState, harness.Router, harness.Tracker, harness.Unlocks).Build("quest:q");

        Assert.Equal(PlanStatus.Satisfied, plan.EntityNodesByKey["quest:q"].Status);
    }

    [Fact]
    public void ItemSourceMetadata_UsesSpawnZonesAndEffectiveLevel()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddItem("item:note", "Note")
            .AddCharacter("character:ghost", "Ghost", level: 4)
            .AddSpawnPoint("spawn:ghost", "Ghost Spawn", scene: "IslandTomb", zone: "Island Tomb")
            .AddZone("zone:islandtomb", "Island Tomb", scene: "IslandTomb")
            .AddEdge("quest:q", "item:note", EdgeType.StepRead)
            .AddEdge("character:ghost", "item:note", EdgeType.DropsItem)
            .AddEdge("character:ghost", "spawn:ghost", EdgeType.HasSpawn)
            .Build();

        // Attach zone median level directly to the spawn node's ZoneKey target.
        var zoneNode = graph.GetNode("zone:islandtomb")!;
        zoneNode.Level = 6;
        var spawn = graph.GetNode("spawn:ghost")!;
        spawn.ZoneKey = "zone:islandtomb";

        var harness = SnapshotHarness.FromSnapshot(graph, new StateSnapshot());
        var statefulBuilder = new QuestPlanBuilder(graph, harness.GameState, harness.Router, harness.Tracker, harness.Unlocks);
        var plan = statefulBuilder.Build("quest:q");

        var ghost = plan.EntityNodesByKey["character:ghost"];
        Assert.NotNull(ghost.SourceZones);
        Assert.Contains("Island Tomb", ghost.SourceZones!);
        Assert.Equal(6, ghost.EffectiveLevel);
    }

    [Fact]
    public void LockedDoor_GetsExplicitUnlockRequirementGroup()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddDoor("door:gate", "Gate", scene: "Town", keyItemKey: "item:key")
            .AddItem("item:key", "Copper Key")
            .AddEdge("quest:q", "door:gate", EdgeType.StepTalk)
            .AddEdge("item:key", "door:gate", EdgeType.UnlocksDoor)
            .Build();

        var harness = SnapshotHarness.FromSnapshot(graph, new StateSnapshot());
        var statefulBuilder = new QuestPlanBuilder(graph, harness.GameState, harness.Router, harness.Tracker, harness.Unlocks);
        var plan = statefulBuilder.Build("quest:q");

        var door = plan.EntityNodesByKey["door:gate"];
        Assert.NotNull(door.UnlockRequirementId);
        var group = Assert.IsType<PlanGroupNode>(plan.GetNode(door.UnlockRequirementId!.Value));
        Assert.Equal(PlanGroupKind.AllOf, group.GroupKind);
        Assert.Contains(group.Outgoing, l => l.ToId == (PlanNodeId)"item:key");
    }
}