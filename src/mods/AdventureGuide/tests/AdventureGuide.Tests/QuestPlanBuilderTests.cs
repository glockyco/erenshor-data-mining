using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class QuestPlanBuilderTests
{
    [Fact]
    public void Build_MakesImplicitQuestGroupsExplicit()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:root", "Root Quest", dbName: "RootQuest")
            .AddQuest("quest:pre", "Prereq Quest", dbName: "PrereqQuest")
            .AddCharacter("character:giverA", "Giver A")
            .AddCharacter("character:giverB", "Giver B")
            .AddCharacter("character:turninA", "Turn-in A")
            .AddCharacter("character:turninB", "Turn-in B")
            .AddItem("item:step", "Step Item")
            .AddEdge("quest:root", "character:giverA", EdgeType.AssignedBy)
            .AddEdge("quest:root", "character:giverB", EdgeType.AssignedBy)
            .AddEdge("quest:root", "quest:pre", EdgeType.RequiresQuest)
            .AddEdge("quest:root", "item:step", EdgeType.StepRead, ordinal: 2)
            .AddEdge("quest:root", "character:turninA", EdgeType.CompletedBy)
            .AddEdge("quest:root", "character:turninB", EdgeType.CompletedBy)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:root");
        var root = plan.EntityNodesByKey["quest:root"];

        Assert.Contains(root.Outgoing, l => l.ToId == (PlanNodeId)"quest:root:assignment:anyof");
        Assert.Contains(root.Outgoing, l => l.ToId == (PlanNodeId)"quest:root:objectives:allof");
        Assert.Contains(root.Outgoing, l => l.ToId == (PlanNodeId)"quest:root:completion:anyof");

        var assignment = (PlanGroupNode)plan.GetNode("quest:root:assignment:anyof")!;
        var objectives = (PlanGroupNode)plan.GetNode("quest:root:objectives:allof")!;
        var prerequisites = (PlanGroupNode)plan.GetNode("quest:root:prerequisites:allof")!;
        var steps = (PlanGroupNode)plan.GetNode("quest:root:steps:allof")!;
        var completion = (PlanGroupNode)plan.GetNode("quest:root:completion:anyof")!;

        Assert.Equal(PlanGroupKind.AnyOf, assignment.GroupKind);
        Assert.Equal("How to start", assignment.Label);
        Assert.Equal(PlanGroupKind.AllOf, objectives.GroupKind);
        Assert.Equal("What to do", objectives.Label);
        Assert.Contains(objectives.Outgoing, l => l.ToId == prerequisites.Id);
        Assert.Contains(objectives.Outgoing, l => l.ToId == steps.Id);
        Assert.Equal(PlanGroupKind.AllOf, prerequisites.GroupKind);
        Assert.Equal(PlanGroupKind.AllOf, steps.GroupKind);
        Assert.Null(steps.Label);
        Assert.Equal(PlanGroupKind.AnyOf, completion.GroupKind);
        Assert.Equal("How to complete", completion.Label);
    }

    [Fact]
    public void Build_GroupsAllAssignmentAndCompletionVariantsUnderPhaseLabels()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:root", "Root Quest", dbName: "RootQuest")
            .AddQuest("quest:chain", "Chain Quest", dbName: "ChainQuest")
            .AddCharacter("character:giver", "Giver")
            .AddItem("item:note", "Note")
            .AddZone("zone:start", "Start Zone")
            .AddCharacter("character:turnin", "Turn In")
            .AddZone("zone:end", "End Zone")
            .AddEdge("quest:root", "character:giver", EdgeType.AssignedBy)
            .AddEdge("quest:root", "item:note", EdgeType.AssignedBy)
            .AddEdge("quest:root", "zone:start", EdgeType.AssignedBy)
            .AddEdge("quest:root", "quest:chain", EdgeType.AssignedBy)
            .AddEdge("quest:root", "character:turnin", EdgeType.CompletedBy)
            .AddEdge("quest:root", "item:note", EdgeType.CompletedBy)
            .AddEdge("quest:root", "zone:end", EdgeType.CompletedBy)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:root");

        var assignment = (PlanGroupNode)plan.GetNode("quest:root:assignment:anyof")!;
        var completion = (PlanGroupNode)plan.GetNode("quest:root:completion:anyof")!;

        Assert.Equal("How to start", assignment.Label);
        Assert.Equal("How to complete", completion.Label);
        Assert.Contains(assignment.Outgoing, l => l.ToId == (PlanNodeId)"character:giver");
        Assert.Contains(assignment.Outgoing, l => l.ToId == (PlanNodeId)"item:note");
        Assert.Contains(assignment.Outgoing, l => l.ToId == (PlanNodeId)"zone:start");
        Assert.Contains(assignment.Outgoing, l => l.ToId == (PlanNodeId)"quest:chain");
        Assert.Contains(completion.Outgoing, l => l.ToId == (PlanNodeId)"character:turnin");
        Assert.Contains(completion.Outgoing, l => l.ToId == (PlanNodeId)"item:note");
        Assert.Contains(completion.Outgoing, l => l.ToId == (PlanNodeId)"zone:end");
    }

    [Fact]
    public void Build_MakesVariantRequiredItemsExplicit()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:root", "Root Quest", dbName: "RootQuest")
            .AddItem("item:a", "Variant A")
            .AddItem("item:b", "Variant B")
            .AddItem("item:c", "Shared C")
            .AddEdge("quest:root", "item:a", EdgeType.RequiresItem, group: "good")
            .AddEdge("quest:root", "item:c", EdgeType.RequiresItem, group: "good")
            .AddEdge("quest:root", "item:b", EdgeType.RequiresItem, group: "bad")
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:root");
        var root = plan.EntityNodesByKey["quest:root"];
        var objectives = (PlanGroupNode)plan.GetNode("quest:root:objectives:allof")!;

        var anyOf = (PlanGroupNode)plan.GetNode("quest:root:required-items:anyof")!;
        Assert.Equal(PlanGroupKind.AnyOf, anyOf.GroupKind);
        Assert.Contains(root.Outgoing, l => l.ToId == objectives.Id);
        Assert.Contains(objectives.Outgoing, l => l.ToId == anyOf.Id);

        var good = (PlanGroupNode)plan.GetNode("quest:root:required-items:good:allof")!;
        var bad = (PlanGroupNode)plan.GetNode("quest:root:required-items:bad:allof")!;
        Assert.Equal(PlanGroupKind.AllOf, good.GroupKind);
        Assert.Equal(PlanGroupKind.AllOf, bad.GroupKind);
        Assert.Contains(anyOf.Outgoing, l => l.ToId == good.Id);
        Assert.Contains(anyOf.Outgoing, l => l.ToId == bad.Id);
    }

    [Fact]
    public void Build_MakesItemSourcesAndRecipeMaterialsExplicit()
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
            .AddEdge("quest:reward", "item:product", EdgeType.RewardsItem)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:reward");

        var item = plan.EntityNodesByKey["item:product"];
        var sourceGroup = (PlanGroupNode)plan.GetNode("item:product:sources:anyof")!;
        var recipe = plan.EntityNodesByKey["recipe:product"];
        var materials = (PlanGroupNode)plan.GetNode("recipe:product:materials:allof")!;

        Assert.Equal(PlanGroupKind.ItemSources, sourceGroup.GroupKind);
        Assert.Contains(item.Outgoing, l => l.ToId == sourceGroup.Id);
        Assert.Contains(sourceGroup.Outgoing, l => l.ToId == recipe.Id && l.EdgeType == EdgeType.CraftedFrom);
        Assert.Contains(sourceGroup.Outgoing, l => l.ToId == (PlanNodeId)"character:dropper" && l.EdgeType == EdgeType.DropsItem);

        // quest:reward is on the build path when item:product is built,
        // so the RewardsItem source becomes a cycle stub.
        var rewardLink = Assert.Single(sourceGroup.Outgoing, l => l.EdgeType == EdgeType.RewardsItem);
        var rewardTarget = plan.GetNode(rewardLink.ToId);
        Assert.NotNull(rewardTarget);
        Assert.Equal(PlanStatus.PrunedCycle, rewardTarget!.Status);

        Assert.Equal(PlanGroupKind.AllOf, materials.GroupKind);
        Assert.Contains(recipe.Outgoing, l => l.ToId == materials.Id);
        Assert.Contains(materials.Outgoing, l => l.ToId == (PlanNodeId)"item:mat" && l.EdgeType == EdgeType.RequiresMaterial);
    }
}