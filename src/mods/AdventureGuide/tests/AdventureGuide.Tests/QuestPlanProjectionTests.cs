using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class QuestPlanProjectionTests
{
    [Fact]
    public void ProjectionBuilder_UsesCanonicalFrontierForTrackerAndNavSeeds()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ")
            .AddCharacter("character:giver", "Giver")
            .AddCharacter("character:target", "Target")
            .AddEdge("quest:q", "character:giver", EdgeType.AssignedBy)
            .AddEdge("quest:q", "character:target", EdgeType.StepKill)
            .AddEdge("quest:q", "character:giver", EdgeType.CompletedBy);

        var snapshot = new StateSnapshot { ActiveQuests = ["QuestQ"] };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);
        var plan = harness.BuildPlan("quest:q");
        var projection = AdventureGuide.Plan.QuestPlanProjectionBuilder.Build(plan, harness.GameState);

        Assert.Single(projection.Frontier);
        Assert.Single(projection.Tracker.Frontier);
        Assert.Single(projection.NavigationSeeds);
        Assert.Equal(projection.Frontier[0].NodeId, projection.Tracker.Frontier[0].NodeId);
        Assert.Equal(projection.Frontier[0].NodeId, projection.NavigationSeeds[0].Frontier.NodeId);
    }
}