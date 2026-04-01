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
    public void LockedCharacterSource_GetsNestedDoorAndKeyRequirements()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddItem("item:note", "Torn Note")
            .AddCharacter("character:ghost", "Ghost")
            .AddDoor("door:gate", "Gate", scene: "IslandTomb", keyItemKey: "item:key")
            .AddItem("item:key", "Copper Key")
            .AddItemBag("bag:key", "Key Cache", scene: "IslandTomb")
            .AddEdge("quest:q", "item:note", EdgeType.StepRead)
            .AddEdge("character:ghost", "item:note", EdgeType.DropsItem)
            .AddEdge("door:gate", "character:ghost", EdgeType.UnlocksCharacter)
            .AddEdge("item:key", "door:gate", EdgeType.UnlocksDoor)
            .AddEdge("bag:key", "item:key", EdgeType.DropsItem)
            .Build();

        var bag = graph.GetNode("bag:key")!;
        bag.X = 2f;
        bag.Y = 0f;
        bag.Z = 3f;

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["QuestQ"],
            CurrentZone = "IslandTomb",
        };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var builder = new QuestPlanBuilder(graph, harness.GameState, harness.Router, harness.Tracker, harness.Unlocks);
        var plan = builder.Build("quest:q");

        var ghost = plan.EntityNodesByKey["character:ghost"];
        Assert.NotNull(ghost.UnlockRequirementId);
        var ghostGroup = Assert.IsType<PlanGroupNode>(plan.GetNode(ghost.UnlockRequirementId!.Value));
        Assert.Contains(ghostGroup.Outgoing, l => l.ToId == (PlanNodeId)"door:gate");

        var door = plan.EntityNodesByKey["door:gate"];
        Assert.NotNull(door.UnlockRequirementId);
        var doorGroup = Assert.IsType<PlanGroupNode>(plan.GetNode(door.UnlockRequirementId!.Value));
        Assert.Contains(doorGroup.Outgoing, l => l.ToId == (PlanNodeId)"item:key");

        var key = plan.EntityNodesByKey["item:key"];
        var sourceGroup = Assert.IsType<PlanGroupNode>(plan.GetNode("item:key:sources:anyof"));
        Assert.Contains(sourceGroup.Outgoing, l => l.ToId == (PlanNodeId)"bag:key");
    }

    [Fact]
    public void CharacterSourceInLockedZone_GetsZoneLineQuestRequirement()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddQuest("quest:gate", "Gate Quest", dbName: "GateQuest")
            .AddItem("item:orders", "Marching Orders")
            .AddCharacter("character:gherist", "Gherist", scene: "ZoneB")
            .AddZone("zone:a", "Zone A", scene: "ZoneA")
            .AddZone("zone:b", "Zone B", scene: "ZoneB")
            .AddZoneLine("zl:ab", "ZL A→B", scene: "ZoneA", destinationZoneKey: "zone:b",
                x: 10, y: 0, z: 5)
            .AddEdge("quest:q", "item:orders", EdgeType.StepRead)
            .AddEdge("character:gherist", "item:orders", EdgeType.DropsItem)
            .AddEdge("zl:ab", "zone:b", EdgeType.ConnectsZones)
            .AddEdge("quest:gate", "zl:ab", EdgeType.UnlocksZoneLine)
            .Build();

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["QuestQ"],
            CurrentZone = "ZoneA",
        };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var builder = new QuestPlanBuilder(graph, harness.GameState, harness.Router, harness.Tracker, harness.Unlocks);
        var plan = builder.Build("quest:q");

        var gherist = plan.EntityNodesByKey["character:gherist"];
        Assert.NotNull(gherist.UnlockRequirementId);
        var group = Assert.IsType<PlanGroupNode>(plan.GetNode(gherist.UnlockRequirementId!.Value));
        Assert.Contains(group.Outgoing, l => l.ToId == (PlanNodeId)"quest:gate");
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


    [Fact]
    public void LockedTravelZone_DropsCurrentQuestFromUnlockRequirementGroup()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:travel", "Travel Quest", dbName: "TravelQuest")
            .AddQuest("quest:gate", "Gate Quest", dbName: "GateQuest")
            .AddZone("zone:a", "Zone A", scene: "ZoneA")
            .AddZone("zone:b", "Zone B", scene: "ZoneB")
            .AddZoneLine("zl:ab", "ZL A→B", scene: "ZoneA", destinationZoneKey: "zone:b",
                x: 10, y: 0, z: 5)
            .AddEdge("quest:travel", "zone:b", EdgeType.StepTravel)
            .AddEdge("zl:ab", "zone:b", EdgeType.ConnectsZones)
            .AddEdge("quest:travel", "zl:ab", EdgeType.UnlocksZoneLine)
            .AddEdge("quest:gate", "zl:ab", EdgeType.UnlocksZoneLine)
            .Build();

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["TravelQuest"],
            CurrentZone = "ZoneA",
        };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var plan = new QuestPlanBuilder(graph, harness.GameState, harness.Router, harness.Tracker, harness.Unlocks)
            .Build("quest:travel");

        var zone = plan.EntityNodesByKey["zone:b"];
        Assert.NotNull(zone.UnlockRequirementId);
        var group = Assert.IsType<PlanGroupNode>(plan.GetNode(zone.UnlockRequirementId!.Value));
        Assert.Contains(group.Outgoing, l => l.ToId == (PlanNodeId)"quest:gate");
        Assert.DoesNotContain(group.Outgoing, l => l.ToId == (PlanNodeId)"quest:travel");
    }
    [Fact]
    public void LockedTravelZone_GetsExplicitUnlockRequirementGroup()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:travel", "Travel Quest", dbName: "TravelQuest")
            .AddQuest("quest:gate", "Gate Quest", dbName: "GateQuest")
            .AddZone("zone:a", "Zone A", scene: "ZoneA")
            .AddZone("zone:b", "Zone B", scene: "ZoneB")
            .AddZoneLine("zl:ab", "ZL A→B", scene: "ZoneA", destinationZoneKey: "zone:b",
                x: 10, y: 0, z: 5)
            .AddEdge("quest:travel", "zone:b", EdgeType.StepTravel)
            .AddEdge("quest:gate", "zl:ab", EdgeType.UnlocksZoneLine)
            .Build();

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["TravelQuest"],
            CurrentZone = "ZoneA",
        };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var plan = new QuestPlanBuilder(graph, harness.GameState, harness.Router, harness.Tracker, harness.Unlocks)
            .Build("quest:travel");

        var zone = plan.EntityNodesByKey["zone:b"];
        Assert.NotNull(zone.UnlockRequirementId);
        var group = Assert.IsType<PlanGroupNode>(plan.GetNode(zone.UnlockRequirementId!.Value));
        Assert.Contains(group.Outgoing, l => l.ToId == (PlanNodeId)"quest:gate");
    }
}