using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Tests.Helpers;
using AdventureGuide.UI.Tree;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class QuestTreeSessionTests
{
    [Fact]
    public void GetRootChildren_MaterializesOnlyTopLevelRefs()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:root", "Root Quest", dbName: "RootQuest")
            .AddQuest("quest:pre", "Prereq Quest", dbName: "PrereqQuest")
            .AddItem("item:step", "Step Item")
            .AddCharacter("character:giver", "Giver")
            .AddCharacter("character:turnin", "Turn In")
            .AddEdge("quest:root", "character:giver", EdgeType.AssignedBy)
            .AddEdge("quest:root", "quest:pre", EdgeType.RequiresQuest)
            .AddEdge("quest:root", "item:step", EdgeType.StepRead)
            .AddEdge("quest:root", "character:turnin", EdgeType.CompletedBy)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:root");
        var session = new QuestTreeSession(plan);

        var roots = session.GetRootChildren();

        Assert.Equal(4, roots.Count);
        Assert.All(roots, r => Assert.Equal(0, r.Depth));
        Assert.All(roots, r => Assert.NotNull(plan.GetNode(r.NodeId)));
    }

    [Fact]
    public void GetChildren_PrunesCyclesAtAnyDepth()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:a", "Quest A", dbName: "QuestA")
            .AddQuest("quest:b", "Quest B", dbName: "QuestB")
            .AddEdge("quest:a", "quest:b", EdgeType.RequiresQuest)
            .AddEdge("quest:b", "quest:a", EdgeType.RequiresQuest)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:a");
        var session = new QuestTreeSession(plan);

        var roots = session.GetRootChildren();
        var prereqGroupForA = Assert.Single(roots);
        var bRef = Assert.Single(session.GetChildren(prereqGroupForA));
        var prereqGroupForB = Assert.Single(session.GetChildren(bRef));
        var childrenOfBPrereqs = session.GetChildren(prereqGroupForB);

        Assert.Empty(childrenOfBPrereqs);
    }

    [Fact]
    public void CanonicalNode_MayAppearAsMultipleVisualRefs()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:root", "Root Quest", dbName: "RootQuest")
            .AddCharacter("character:npc", "Shared NPC")
            .AddEdge("quest:root", "character:npc", EdgeType.AssignedBy)
            .AddEdge("quest:root", "character:npc", EdgeType.CompletedBy)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:root");
        var session = new QuestTreeSession(plan);

        var roots = session.GetRootChildren();
        var assignmentGroup = roots.First(r => r.NodeId == (PlanNodeId)"quest:root:assignment:anyof");
        var completionGroup = roots.First(r => r.NodeId == (PlanNodeId)"quest:root:completion:anyof");

        var assignmentNpc = Assert.Single(session.GetChildren(assignmentGroup));
        var completionNpc = Assert.Single(session.GetChildren(completionGroup));

        Assert.Equal((PlanNodeId)"character:npc", assignmentNpc.NodeId);
        Assert.Equal((PlanNodeId)"character:npc", completionNpc.NodeId);
        Assert.NotEqual(assignmentNpc.Id, completionNpc.Id);
    }
}