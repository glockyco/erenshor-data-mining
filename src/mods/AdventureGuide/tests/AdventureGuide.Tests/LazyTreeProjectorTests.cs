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
        Assert.Single(secondLevel);
        Assert.Equal((PlanNodeId)"item:mat", secondLevel[0].NodeId);
    }
}