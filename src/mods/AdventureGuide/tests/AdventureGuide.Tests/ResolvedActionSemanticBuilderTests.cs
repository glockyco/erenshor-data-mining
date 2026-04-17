using AdventureGuide.Graph;
using AdventureGuide.Navigation;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

/// <summary>
/// Unit tests for <see cref="ResolvedActionSemanticBuilder"/> focusing on
/// <c>RationaleText</c> correctness for direct and transitive crafting sources.
/// </summary>
public sealed class ResolvedActionSemanticBuilderTests
{
    // -- helpers -----------------------------------------------------------------

    private static ResolvedNodeContext Context(Node node, EdgeType? edgeType = null) =>
        new(node.Key, node, edgeType);

    // -- rationale text tests ----------------------------------------------------

    [Fact]
    public void BuildRationaleText_DirectMineSource_ShowsDirectItem()
    {
        // Mineral Deposit yields Iron Ore directly.
        // goalNode  = Iron Ore  (the item being collected)
        // targetNode = Mineral Deposit, edge = YieldsItem
        var guide = new CompiledGuideBuilder()
            .AddItem("item:iron-ore")
            .AddMiningNode("node:mineral-deposit", scene: "ZoneA")
            .AddEdge("node:mineral-deposit", "item:iron-ore", EdgeType.YieldsItem)
            .Build();

        var ironOre = guide.GetNode("item:iron-ore")!;
        var deposit = guide.GetNode("node:mineral-deposit")!;
        var goalNode = Context(ironOre);
        var targetNode = Context(deposit, EdgeType.YieldsItem);

        var semantic = ResolvedActionSemanticBuilder.Build(guide, ironOre, goalNode, targetNode);

        Assert.Equal("Drops item:iron-ore", semantic.RationaleText);
    }

    [Fact]
    public void BuildRationaleText_CraftingChain_ShowsIngredientNotFinalItem()
    {
        // Ghostly Key is crafted from Iron Ore which is yielded by Mineral Deposit.
        // When resolving targets for Ghostly Key, the deposit source is found
        // transitively. The semantic must say "Drops item:iron-ore" (what the deposit
        // actually provides), not "Drops item:ghostly-key" (the final crafted item).
        //
        // This test simulates the goalNode being set to the DIRECT item (Iron Ore)
        // as done by ResolveItemTargetsFromBlueprint after commit 2, rather than
        // the top-level item (Ghostly Key).
        var guide = new CompiledGuideBuilder()
            .AddItem("item:ghostly-key")
            .AddItem("item:iron-ore")
            .AddMiningNode("node:mineral-deposit", scene: "ZoneA")
            .AddEdge("item:ghostly-key", "recipe:ghostly-key", EdgeType.CraftedFrom)
            .AddEdge("recipe:ghostly-key", "item:iron-ore", EdgeType.RequiresMaterial)
            .AddEdge("node:mineral-deposit", "item:iron-ore", EdgeType.YieldsItem)
            .Build();

        var ghostlyKey = guide.GetNode("item:ghostly-key")!;
        var ironOre = guide.GetNode("item:iron-ore")!;
        var deposit = guide.GetNode("node:mineral-deposit")!;

        // goalNode = Iron Ore (the direct item this source provides, not Ghostly Key)
        var goalNode = Context(ironOre);
        var targetNode = Context(deposit, EdgeType.YieldsItem);

        var semantic = ResolvedActionSemanticBuilder.Build(guide, ghostlyKey, goalNode, targetNode);

        Assert.Equal("Drops item:iron-ore", semantic.RationaleText);
        Assert.NotEqual("Drops item:ghostly-key", semantic.RationaleText);
    }

    [Fact]
    public void BuildRationaleText_WrongGoalNode_WouldShowFinalItem()
    {
        // Negative test: if goalNode were incorrectly set to Ghostly Key (the old bug),
        // the rationale would say "Drops item:ghostly-key". This confirms the fix relies
        // on the caller providing the direct item as goalNode.
        var guide = new CompiledGuideBuilder()
            .AddItem("item:ghostly-key")
            .AddItem("item:iron-ore")
            .AddMiningNode("node:mineral-deposit", scene: "ZoneA")
            .Build();

        var ghostlyKey = guide.GetNode("item:ghostly-key")!;
        var deposit = guide.GetNode("node:mineral-deposit")!;

        // Incorrect: goalNode = Ghostly Key (simulates the old behaviour)
        var goalNode = Context(ghostlyKey);
        var targetNode = Context(deposit, EdgeType.YieldsItem);

        var semantic = ResolvedActionSemanticBuilder.Build(guide, ghostlyKey, goalNode, targetNode);

        // This is the wrong output -- here to document the buggy behaviour and
        // confirm the fix lives in the caller, not in BuildRationaleText itself.
        Assert.Equal("Drops item:ghostly-key", semantic.RationaleText);
    }
}
