using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
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
}