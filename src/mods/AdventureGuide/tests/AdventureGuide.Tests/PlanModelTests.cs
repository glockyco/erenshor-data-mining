using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Plan.Semantics;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class PlanModelTests
{
    [Fact]
    public void DependencySemantics_QuestGiversAndCompletions_AreExplicitAnyOfGroups()
    {
        var assigned = DependencySemantics.FromEdge(EdgeType.AssignedBy);
        var completed = DependencySemantics.FromEdge(EdgeType.CompletedBy);

        Assert.Equal(DependencySemanticKind.AssignmentSource, assigned.Kind);
        Assert.Equal(DependencyPhase.Acceptance, assigned.Phase);
        Assert.Equal(PlanStructuralKind.Need, assigned.StructuralKind);
        Assert.Equal(GroupDisplayHint.UsuallyFlatten, assigned.GroupDisplayHint);

        Assert.Equal(DependencySemanticKind.CompletionTarget, completed.Kind);
        Assert.Equal(DependencyPhase.Completion, completed.Phase);
        Assert.Equal(PlanStructuralKind.Need, completed.StructuralKind);
        Assert.Equal(GroupDisplayHint.UsuallyFlatten, completed.GroupDisplayHint);
    }

    [Fact]
    public void DependencySemantics_ObjectiveAndSourceSemantics_DoNotDriftAcrossEdgeTypes()
    {
        var requiresItem = DependencySemantics.FromEdge(EdgeType.RequiresItem);
        var requiresMaterial = DependencySemantics.FromEdge(EdgeType.RequiresMaterial);
        var dropsItem = DependencySemantics.FromEdge(EdgeType.DropsItem);
        var craftedFrom = DependencySemantics.FromEdge(EdgeType.CraftedFrom);
        var unlocksDoor = DependencySemantics.FromEdge(EdgeType.UnlocksDoor);

        Assert.Equal(DependencyPhase.Objective, requiresItem.Phase);
        Assert.Equal(PlanStructuralKind.Need, requiresItem.StructuralKind);

        Assert.Equal(DependencyPhase.Objective, requiresMaterial.Phase);
        Assert.Equal(GroupDisplayHint.UsuallyShow, requiresMaterial.GroupDisplayHint);

        Assert.Equal(DependencyPhase.Source, dropsItem.Phase);
        Assert.Equal(PlanStructuralKind.Provide, dropsItem.StructuralKind);
        Assert.Equal(GroupDisplayHint.UsuallyFlatten, dropsItem.GroupDisplayHint);

        Assert.Equal(DependencyPhase.Source, craftedFrom.Phase);
        Assert.Equal(PlanStructuralKind.Provide, craftedFrom.StructuralKind);
        Assert.Equal(GroupDisplayHint.UsuallyShow, craftedFrom.GroupDisplayHint);

        Assert.Equal(DependencyPhase.Unlock, unlocksDoor.Phase);
        Assert.Equal(PlanStructuralKind.Gate, unlocksDoor.StructuralKind);
    }

    [Fact]
    public void QuestPlan_PreservesCanonicalEntityIdentity()
    {
        var quest = new Node
        {
            Key = "quest:test",
            Type = NodeType.Quest,
            DisplayName = "Test Quest",
            DbName = "TestQuest",
        };
        var item = new Node
        {
            Key = "item:test",
            Type = NodeType.Item,
            DisplayName = "Test Item",
        };

        var questPlanNode = new PlanEntityNode("quest:test", quest);
        var itemPlanNode = new PlanEntityNode("item:test", item);
        var group = new PlanGroupNode("group:anyof:test", PlanGroupKind.AnyOf, "Any of");
        var linkA = new PlanLink(group.Id, itemPlanNode.Id, DependencySemantics.FromEdge(EdgeType.DropsItem), EdgeType.DropsItem);
        var linkB = new PlanLink(questPlanNode.Id, group.Id, DependencySemantics.FromEdge(EdgeType.RequiresItem), EdgeType.RequiresItem);
        group.Outgoing.Add(linkA);
        questPlanNode.Outgoing.Add(linkB);

        var frontier = new[] { new FrontierRef(questPlanNode.Id, itemPlanNode.Id, linkA) };
        var tracker = new TrackerProjection(frontier);
        var navSeeds = new[] { new NavCandidateSeed(questPlanNode.Id, frontier[0]) };

        var plan = new QuestPlan(
            questPlanNode.Id,
            new Dictionary<PlanNodeId, PlanNode>
            {
                [questPlanNode.Id] = questPlanNode,
                [itemPlanNode.Id] = itemPlanNode,
                [group.Id] = group,
            },
            new Dictionary<string, PlanEntityNode>
            {
                [questPlanNode.NodeKey] = questPlanNode,
                [itemPlanNode.NodeKey] = itemPlanNode,
            },
            new Dictionary<PlanNodeId, PlanGroupNode>
            {
                [group.Id] = group,
            },
            frontier,
            tracker,
            navSeeds);

        Assert.Same(itemPlanNode, plan.EntityNodesByKey["item:test"]);
        Assert.Same(itemPlanNode, plan.GetNode("item:test"));
        Assert.Same(group, plan.GroupNodes[group.Id]);
        Assert.Single(plan.NavigationSeeds);
        Assert.Single(plan.Tracker.Frontier);
    }
}