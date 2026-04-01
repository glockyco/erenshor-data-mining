using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Tests.Helpers;
using AdventureGuide.UI.Tree;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class LazyTreeProjectorTests
{
    [Fact]
    public void Projector_FlattensStructuralGroupsAtRoot()
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
        var projector = new LazyTreeProjector(plan, session);

        var roots = projector.GetRootChildren();

        Assert.Equal(4, roots.Count);
        Assert.All(roots, r => Assert.IsType<PlanEntityNode>(plan.GetNode(r.NodeId)));
        Assert.Contains(roots, r => r.NodeId == (PlanNodeId)"character:giver");
        Assert.Contains(roots, r => r.NodeId == (PlanNodeId)"quest:pre");
        Assert.Contains(roots, r => r.NodeId == (PlanNodeId)"item:step");
        Assert.Contains(roots, r => r.NodeId == (PlanNodeId)"character:turnin");
    }

    [Fact]
    public void Projector_FlattensNestedSourceAndMaterialGroups()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:reward", "Reward Quest", dbName: "RewardQuest")
            .AddItem("item:product", "Product")
            .AddRecipe("recipe:product", "Recipe")
            .AddItem("item:mat", "Material")
            .AddCharacter("character:dropper", "Dropper")
            .AddEdge("quest:reward", "item:product", EdgeType.StepRead)
            .AddEdge("item:product", "recipe:product", EdgeType.CraftedFrom)
            .AddEdge("recipe:product", "item:mat", EdgeType.RequiresMaterial)
            .AddEdge("character:dropper", "item:product", EdgeType.DropsItem)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:reward");
        var session = new QuestTreeSession(plan);
        var projector = new LazyTreeProjector(plan, session);

        var productRef = projector.GetRootChildren().Single(r => r.NodeId == (PlanNodeId)"item:product");
        var firstLevel = projector.GetChildren(productRef);

        Assert.Contains(firstLevel, r => r.NodeId == (PlanNodeId)"recipe:product");
        Assert.Contains(firstLevel, r => r.NodeId == (PlanNodeId)"character:dropper");

        var recipeRef = firstLevel.Single(r => r.NodeId == (PlanNodeId)"recipe:product");
        var secondLevel = projector.GetChildren(recipeRef);
        var materialsGroup = Assert.Single(secondLevel);
        Assert.Equal((PlanNodeId)"recipe:product:materials:allof", materialsGroup.NodeId);

        var thirdLevel = projector.GetChildren(materialsGroup);
        Assert.Single(thirdLevel);
        Assert.Equal((PlanNodeId)"item:mat", thirdLevel[0].NodeId);
    }

    [Fact]
    public void Projector_PrunesCrossTypeCyclesWithoutRenderingPlaceholders()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:note", "Wyland's Note", dbName: "WylandsNote")
            .AddItem("item:torn-note", "Torn Note")
            .AddQuest("quest:orders", "Marching Orders", dbName: "MarchingOrders")
            .AddEdge("quest:note", "item:torn-note", EdgeType.StepRead)
            .AddEdge("quest:orders", "item:torn-note", EdgeType.RewardsItem)
            .AddEdge("quest:orders", "quest:note", EdgeType.RequiresQuest)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:note");
        var session = new QuestTreeSession(plan);
        var projector = new LazyTreeProjector(plan, session);

        var tornNoteRef = Assert.Single(projector.GetRootChildren());
        Assert.Equal((PlanNodeId)"item:torn-note", tornNoteRef.NodeId);

        var itemChildren = projector.GetChildren(tornNoteRef);
        var ordersRef = Assert.Single(itemChildren);
        Assert.Equal((PlanNodeId)"quest:orders", ordersRef.NodeId);

        var ordersChildren = projector.GetChildren(ordersRef);
        Assert.Empty(ordersChildren);
    }
}
