using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class PlanFrontierResolverTests
{
    [Fact]
    public void AcceptanceGatesObjectives()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddCharacter("character:giver", "Giver")
            .AddCharacter("character:target", "Target")
            .AddEdge("quest:q", "character:giver", EdgeType.AssignedBy)
            .AddEdge("quest:q", "character:target", EdgeType.StepKill)
            .AddEdge("quest:q", "character:giver", EdgeType.CompletedBy);

        var harness = SnapshotHarness.FromGraph(builder);
        var plan = harness.BuildPlan("quest:q");
        var frontier = harness.ComputePlanFrontier(plan);

        Assert.Contains(frontier, f => f.NodeId == (AdventureGuide.Plan.PlanNodeId)"character:giver");
        Assert.DoesNotContain(frontier, f => f.NodeId == (AdventureGuide.Plan.PlanNodeId)"character:target");
    }

    [Fact]
    public void ObjectivesConcurrent()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddCharacter("character:a", "Mob A")
            .AddCharacter("character:b", "Mob B")
            .AddCharacter("character:giver", "Giver")
            .AddCharacter("character:turnin", "Turn In")
            .AddEdge("quest:q", "character:giver", EdgeType.AssignedBy)
            .AddEdge("quest:q", "character:a", EdgeType.StepKill)
            .AddEdge("quest:q", "character:b", EdgeType.StepKill)
            .AddEdge("quest:q", "character:turnin", EdgeType.CompletedBy);

        var snapshot = new StateSnapshot { ActiveQuests = ["QuestQ"] };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var frontier = harness.ComputePlanFrontier(harness.BuildPlan("quest:q"));

        Assert.Contains(frontier, f => f.NodeId == (AdventureGuide.Plan.PlanNodeId)"character:a");
        Assert.Contains(frontier, f => f.NodeId == (AdventureGuide.Plan.PlanNodeId)"character:b");
    }

    [Fact]
    public void TurnInAppearsWhenNoObjectives()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddCharacter("character:giver", "Giver")
            .AddCharacter("character:turnin", "Turn In")
            .AddEdge("quest:q", "character:giver", EdgeType.AssignedBy)
            .AddEdge("quest:q", "character:turnin", EdgeType.CompletedBy);

        var snapshot = new StateSnapshot { ActiveQuests = ["QuestQ"] };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var frontier = harness.ComputePlanFrontier(harness.BuildPlan("quest:q"));

        Assert.Contains(frontier, f => f.NodeId == (AdventureGuide.Plan.PlanNodeId)"character:turnin");
    }

    [Fact]
    public void CompletedSubquestSkipped()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddQuest("quest:p", "Quest P", dbName: "QuestP")
            .AddCharacter("character:giver", "Giver")
            .AddCharacter("character:turnin", "Turn In")
            .AddCharacter("character:mob", "Mob")
            .AddCharacter("character:p_giver", "P Giver")
            .AddCharacter("character:p_target", "P Target")
            .AddEdge("quest:q", "character:giver", EdgeType.AssignedBy)
            .AddEdge("quest:q", "quest:p", EdgeType.RequiresQuest)
            .AddEdge("quest:q", "character:mob", EdgeType.StepKill)
            .AddEdge("quest:q", "character:turnin", EdgeType.CompletedBy)
            .AddEdge("quest:p", "character:p_giver", EdgeType.AssignedBy)
            .AddEdge("quest:p", "character:p_target", EdgeType.StepKill)
            .AddEdge("quest:p", "character:p_giver", EdgeType.CompletedBy);

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["QuestQ"],
            CompletedQuests = ["QuestP"],
        };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var frontier = harness.ComputePlanFrontier(harness.BuildPlan("quest:q"));

        Assert.DoesNotContain(frontier, f => f.NodeId == (AdventureGuide.Plan.PlanNodeId)"character:p_giver");
        Assert.DoesNotContain(frontier, f => f.NodeId == (AdventureGuide.Plan.PlanNodeId)"character:p_target");
        Assert.Contains(frontier, f => f.NodeId == (AdventureGuide.Plan.PlanNodeId)"character:mob");
    }

    [Fact]
    public void ItemQuantitySatisfied_ShowsTurnIn()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddItem("item:ore", "Ore")
            .AddCharacter("character:giver", "Giver")
            .AddCharacter("character:turnin", "Turn In")
            .AddEdge("quest:q", "character:giver", EdgeType.AssignedBy)
            .AddEdge("quest:q", "item:ore", EdgeType.RequiresItem, quantity: 3)
            .AddEdge("quest:q", "character:turnin", EdgeType.CompletedBy);

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["QuestQ"],
            Inventory = new Dictionary<string, int> { ["item:ore"] = 3 },
        };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var frontier = harness.ComputePlanFrontier(harness.BuildPlan("quest:q"));

        Assert.DoesNotContain(frontier, f => f.NodeId == (AdventureGuide.Plan.PlanNodeId)"item:ore");
        Assert.Contains(frontier, f => f.NodeId == (AdventureGuide.Plan.PlanNodeId)"character:turnin");
    }

    [Fact]
    public void ItemQuantityNotMet_ShowsItemObjective()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddItem("item:ore", "Ore")
            .AddCharacter("character:giver", "Giver")
            .AddCharacter("character:turnin", "Turn In")
            .AddEdge("quest:q", "character:giver", EdgeType.AssignedBy)
            .AddEdge("quest:q", "item:ore", EdgeType.RequiresItem, quantity: 3)
            .AddEdge("quest:q", "character:turnin", EdgeType.CompletedBy);

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["QuestQ"],
            Inventory = new Dictionary<string, int> { ["item:ore"] = 2 },
        };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var frontier = harness.ComputePlanFrontier(harness.BuildPlan("quest:q"));

        Assert.Contains(frontier, f => f.NodeId == (AdventureGuide.Plan.PlanNodeId)"item:ore");
        Assert.DoesNotContain(frontier, f => f.NodeId == (AdventureGuide.Plan.PlanNodeId)"character:turnin");
    }

    // ── IsImplicitFrontierBlocked tests ───────────────────────────────────────

    [Fact]
    public void IsImplicitFrontierBlocked_ObjectiveLockedByUnlockRequirement_ReturnsTrue()
    {
        // Character sits behind a door; door needs item:key; key not in inventory.
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddCharacter("character:mob", "Mob")
            .AddDoor("door:gate", "Gate", scene: "Town", keyItemKey: "item:key")
            .AddItem("item:key", "Key")
            .AddEdge("quest:q", "character:mob", EdgeType.StepKill)
            .AddEdge("door:gate", "character:mob", EdgeType.UnlocksCharacter)
            .AddEdge("item:key", "door:gate", EdgeType.UnlocksDoor);

        var snapshot = new StateSnapshot { ActiveQuests = ["QuestQ"] };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var plan = harness.BuildPlan("quest:q");
        var projection = QuestPlanProjectionBuilder.Build(plan, harness.GameState);

        Assert.True(FrontierResolver.IsImplicitFrontierBlocked(projection));
    }

    [Fact]
    public void IsImplicitFrontierBlocked_ObjectiveNoLock_ReturnsFalse()
    {
        // Character has no unlock requirement — freely accessible.
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddCharacter("character:mob", "Mob")
            .AddEdge("quest:q", "character:mob", EdgeType.StepKill);

        var snapshot = new StateSnapshot { ActiveQuests = ["QuestQ"] };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var plan = harness.BuildPlan("quest:q");
        var projection = QuestPlanProjectionBuilder.Build(plan, harness.GameState);

        Assert.False(FrontierResolver.IsImplicitFrontierBlocked(projection));
    }

    [Fact]
    public void IsImplicitFrontierBlocked_ObjectiveDoorNowOpen_ReturnsFalse()
    {
        // Character is behind a door, but the door is already open in live state.
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddCharacter("character:mob", "Mob")
            .AddDoor("door:gate", "Gate", scene: "Town", keyItemKey: "item:key")
            .AddItem("item:key", "Key")
            .AddEdge("quest:q", "character:mob", EdgeType.StepKill)
            .AddEdge("door:gate", "character:mob", EdgeType.UnlocksCharacter)
            .AddEdge("item:key", "door:gate", EdgeType.UnlocksDoor);

        // Door is open: the state resolver reports Unlocked so the evaluator
        // sees no blocking source, and UnlockRequirementId is not set.
        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["QuestQ"],
            LiveNodeStates = { ["door:gate"] = new LiveNodeState { State = "door_unlocked", IsSatisfied = true } },
        };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var plan = harness.BuildPlan("quest:q");
        var projection = QuestPlanProjectionBuilder.Build(plan, harness.GameState);

        Assert.False(FrontierResolver.IsImplicitFrontierBlocked(projection));
    }

    [Fact]
    public void IsImplicitFrontierBlocked_AcceptancePhase_BlockedOnlyWhenAllPathsBlocked()
    {
        // Two givers for an implicit quest: one locked, one free.
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ", implicit_: true)
            .AddCharacter("character:giver1", "Giver 1")
            .AddCharacter("character:giver2", "Giver 2")
            .AddDoor("door:gate", "Gate", scene: "Town", keyItemKey: "item:key")
            .AddItem("item:key", "Key")
            .AddEdge("quest:q", "character:giver1", EdgeType.AssignedBy)
            .AddEdge("quest:q", "character:giver2", EdgeType.AssignedBy)
            .AddEdge("door:gate", "character:giver1", EdgeType.UnlocksCharacter)
            .AddEdge("item:key", "door:gate", EdgeType.UnlocksDoor);

        // Key not held — giver1 is blocked, giver2 is free.
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), new StateSnapshot());
        var plan = harness.BuildPlan("quest:q");
        var projection = QuestPlanProjectionBuilder.Build(plan, harness.GameState);

        // Acceptance phase: not ALL paths blocked → should NOT suppress markers.
        Assert.False(FrontierResolver.IsImplicitFrontierBlocked(projection));
    }

    [Fact]
    public void IsImplicitFrontierBlocked_AcceptancePhase_AllPathsBlocked_ReturnsTrue()
    {
        // Single locked giver: the only acceptance path is blocked.
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ", implicit_: true)
            .AddCharacter("character:giver", "Giver")
            .AddDoor("door:gate", "Gate", scene: "Town", keyItemKey: "item:key")
            .AddItem("item:key", "Key")
            .AddEdge("quest:q", "character:giver", EdgeType.AssignedBy)
            .AddEdge("door:gate", "character:giver", EdgeType.UnlocksCharacter)
            .AddEdge("item:key", "door:gate", EdgeType.UnlocksDoor);

        var harness = SnapshotHarness.FromSnapshot(builder.Build(), new StateSnapshot());
        var plan = harness.BuildPlan("quest:q");
        var projection = QuestPlanProjectionBuilder.Build(plan, harness.GameState);

        Assert.True(FrontierResolver.IsImplicitFrontierBlocked(projection));
    }
}