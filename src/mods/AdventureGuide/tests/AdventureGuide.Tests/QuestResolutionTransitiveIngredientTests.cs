using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class QuestResolutionTransitiveIngredientTests
{
    [Fact]
    public void HasObjectiveOccurrence_SkipsSatisfiedTransitiveIngredient()
    {
        var harness = SnapshotHarness.FromSnapshot(
            BuildCraftGraph(),
            new StateSnapshot
            {
                CurrentZone = "ZoneA",
                ActiveQuests = new List<string> { "Quest Test" },
                Inventory = new Dictionary<string, int>
                {
                    ["item:ore - iron ore"] = 1,
                },
            });

        var plan = harness.BuildPlan("quest:test");

        Assert.False(FrontierResolver.HasObjectiveOccurrence(
            plan,
            harness.GameState,
            "item:ore - iron ore"));
        Assert.True(FrontierResolver.HasObjectiveOccurrence(
            plan,
            harness.GameState,
            "item:mold"));
    }

    [Fact]
    public void HasObjectiveOccurrence_IncludesUnsatisfiedTransitiveIngredient()
    {
        var harness = SnapshotHarness.FromSnapshot(
            BuildCraftGraph(),
            new StateSnapshot
            {
                CurrentZone = "ZoneA",
                ActiveQuests = new List<string> { "Quest Test" },
            });

        var plan = harness.BuildPlan("quest:test");

        Assert.True(FrontierResolver.HasObjectiveOccurrence(
            plan,
            harness.GameState,
            "item:ore - iron ore"));
        Assert.True(FrontierResolver.HasObjectiveOccurrence(
            plan,
            harness.GameState,
            "item:mold"));
    }

    private static EntityGraph BuildCraftGraph()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:test", "Quest Test", dbName: "Quest Test", scene: "ZoneA")
            .AddItem("item:key", "Ghost Key")
            .AddItem("item:mold", "Ghost Key Mold")
            .AddItem("item:ore - iron ore", "Chunk of Iron Ore")
            .AddRecipe("recipe:key", "Ghost Key Recipe")
            .AddMiningNode("mining:mold-source", "Mineral Deposit", scene: "ZoneA")
            .AddMiningNode("mining:ore-source", "Mineral Deposit", scene: "ZoneA")
            .AddEdge("quest:test", "item:key", EdgeType.RequiresItem, quantity: 1)
            .AddEdge("item:key", "recipe:key", EdgeType.CraftedFrom)
            .AddEdge("recipe:key", "item:mold", EdgeType.RequiresMaterial, quantity: 1)
            .AddEdge("recipe:key", "item:ore - iron ore", EdgeType.RequiresMaterial, quantity: 1)
            .AddEdge("mining:mold-source", "item:mold", EdgeType.YieldsItem)
            .AddEdge("mining:ore-source", "item:ore - iron ore", EdgeType.YieldsItem)
            .Build();

        graph.GetNode("mining:mold-source")!.X = 10f;
        graph.GetNode("mining:mold-source")!.Y = 0f;
        graph.GetNode("mining:mold-source")!.Z = 10f;
        graph.GetNode("mining:ore-source")!.X = 20f;
        graph.GetNode("mining:ore-source")!.Y = 0f;
        graph.GetNode("mining:ore-source")!.Z = 20f;
        return graph;
    }
}
