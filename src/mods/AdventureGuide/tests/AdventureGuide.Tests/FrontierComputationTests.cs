using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

/// <summary>
/// Tests for <see cref="Frontier.FrontierComputer.ComputeFrontier"/>:
/// three-phase child processing (acceptance → objectives → turn-in),
/// item quantity thresholds, and sub-quest pruning.
/// </summary>
public class FrontierComputationTests
{
    /// <summary>
    /// Quest not started. AssignedBy edge → Acceptance role, which gates
    /// all objectives. Frontier should contain the assigner, not the step target.
    /// </summary>
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

        // Empty state → quest is NotStarted.
        var harness = SnapshotHarness.FromGraph(builder);
        var tree = harness.BuildViewTree("quest:q");
        Assert.NotNull(tree);

        var frontier = harness.ComputeFrontier(tree);

        ViewTreeAssert.FrontierContains(frontier, "character:giver");
        ViewTreeAssert.FrontierDoesNotContain(frontier, "character:target");
    }

    /// <summary>
    /// Quest is active with two concurrent StepKill targets.
    /// Both should appear in the frontier simultaneously.
    /// </summary>
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
        var tree = harness.BuildViewTree("quest:q");
        Assert.NotNull(tree);

        var frontier = harness.ComputeFrontier(tree);

        ViewTreeAssert.FrontierContains(frontier, "character:a");
        ViewTreeAssert.FrontierContains(frontier, "character:b");
    }

    /// <summary>
    /// Quest is active with one incomplete StepKill. Turn-in should NOT
    /// appear — it's deferred until all objectives are satisfied.
    /// </summary>
    [Fact]
    public void TurnInDeferredUntilObjectivesDone()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddCharacter("character:mob", "Mob")
            .AddCharacter("character:giver", "Giver")
            .AddCharacter("character:turnin", "Turn In")
            .AddEdge("quest:q", "character:giver", EdgeType.AssignedBy)
            .AddEdge("quest:q", "character:mob", EdgeType.StepKill)
            .AddEdge("quest:q", "character:turnin", EdgeType.CompletedBy);

        var snapshot = new StateSnapshot { ActiveQuests = ["QuestQ"] };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var tree = harness.BuildViewTree("quest:q");
        Assert.NotNull(tree);

        var frontier = harness.ComputeFrontier(tree);

        ViewTreeAssert.FrontierContains(frontier, "character:mob");
        ViewTreeAssert.FrontierDoesNotContain(frontier, "character:turnin");
    }

    /// <summary>
    /// Quest is active with only a CompletedBy edge (no step children).
    /// Since there are no objectives to gate it, the turn-in should
    /// appear directly in the frontier.
    /// </summary>
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
        var tree = harness.BuildViewTree("quest:q");
        Assert.NotNull(tree);

        var frontier = harness.ComputeFrontier(tree);

        ViewTreeAssert.FrontierContains(frontier, "character:turnin");
    }

    /// <summary>
    /// Quest Q requires Quest P (RequiresQuest). P is completed.
    /// P's sub-tree should be pruned (Done) — none of P's children
    /// should appear in Q's frontier.
    /// </summary>
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
            // P's own structure
            .AddEdge("quest:p", "character:p_giver", EdgeType.AssignedBy)
            .AddEdge("quest:p", "character:p_target", EdgeType.StepKill)
            .AddEdge("quest:p", "character:p_giver", EdgeType.CompletedBy);

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["QuestQ"],
            CompletedQuests = ["QuestP"],
        };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var tree = harness.BuildViewTree("quest:q");
        Assert.NotNull(tree);

        var frontier = harness.ComputeFrontier(tree);

        // P is Done → its children should not leak into Q's frontier.
        ViewTreeAssert.FrontierDoesNotContain(frontier, "character:p_giver");
        ViewTreeAssert.FrontierDoesNotContain(frontier, "character:p_target");
        // Q's own objectives should still be there.
        ViewTreeAssert.FrontierContains(frontier, "character:mob");
    }

    /// <summary>
    /// Quest requires 3x of an item. Player has exactly 3.
    /// Item should be Done (not Objective). With the only objective
    /// satisfied, the turn-in should appear.
    /// </summary>
    [Fact]
    public void ItemQuantitySatisfied()
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
        var tree = harness.BuildViewTree("quest:q");
        Assert.NotNull(tree);

        var frontier = harness.ComputeFrontier(tree);

        ViewTreeAssert.FrontierDoesNotContain(frontier, "item:ore");
        ViewTreeAssert.FrontierContains(frontier, "character:turnin");
    }

    /// <summary>
    /// Quest requires 3x of an item. Player has only 2.
    /// Item should be Objective, turn-in should be deferred.
    /// </summary>
    [Fact]
    public void ItemQuantityNotMet()
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
        var tree = harness.BuildViewTree("quest:q");
        Assert.NotNull(tree);

        var frontier = harness.ComputeFrontier(tree);

        ViewTreeAssert.FrontierContains(frontier, "item:ore");
        ViewTreeAssert.FrontierDoesNotContain(frontier, "character:turnin");
    }
}
