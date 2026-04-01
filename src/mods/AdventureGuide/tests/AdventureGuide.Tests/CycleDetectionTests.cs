using AdventureGuide.Graph;
using AdventureGuide.Tests.Helpers;
using AdventureGuide.Views;
using Xunit;

namespace AdventureGuide.Tests;

/// <summary>
/// Verifies the three-colour DFS in <see cref="QuestViewBuilder"/> correctly
/// detects back-edges, marks cycle refs, propagates infeasibility, and
/// distinguishes harmless cross-edges from true structural cycles.
/// </summary>
public class CycleDetectionTests
{
    /// <summary>
    /// A → requires B, B → requires A. Direct mutual dependency.
    /// Building from A should detect the back-edge to A when expanding B,
    /// making B infeasible (prerequisite is back-edge), which propagates
    /// back to A (prerequisite B is infeasible).
    /// </summary>
    [Fact]
    public void SimpleQuestCycle()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:a", "Quest A", dbName: "QuestA", implicit_: true)
            .AddQuest("quest:b", "Quest B", dbName: "QuestB", implicit_: true)
            .AddEdge("quest:a", "quest:b", EdgeType.RequiresQuest)
            .AddEdge("quest:b", "quest:a", EdgeType.RequiresQuest);

        var harness = SnapshotHarness.FromGraph(builder);
        var tree = harness.BuildViewTree("quest:a");

        Assert.NotNull(tree);
        // Root quest A should be marked infeasible due to the cycle.
        Assert.True(tree!.IsCycleRef, "Quest A should be infeasible (cycle ref)");
    }

    /// <summary>
    /// Quest Q has a StepRead for Item I. Item I's only source is
    /// RewardsItem from Quest Q itself. Expanding I's sources finds Q
    /// on the grey set (back-edge). The item has no viable source,
    /// so IsSupportSubtreeInfeasible prunes it. AddStepChildren skips
    /// infeasible children, so item:i does not appear in the tree.
    /// </summary>
    [Fact]
    public void SelfReferencingQuestReward()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Quest Q", dbName: "QuestQ", implicit_: true)
            .AddItem("item:i", "Reward Item")
            .AddEdge("quest:q", "item:i", EdgeType.StepRead)
            .AddEdge("quest:q", "item:i", EdgeType.RewardsItem);

        var harness = SnapshotHarness.FromGraph(builder);
        var tree = harness.BuildViewTree("quest:q");

        Assert.NotNull(tree);
        // Item I's only source is quest:q (back-edge), making the item
        // infeasible. Infeasible step children are pruned from the tree.
        ViewTreeAssert.HasNoChild(tree!, "item:i");
    }

    /// <summary>
    /// DAG (not a cycle): P requires A, P requires B, both A and B require C.
    /// C is expanded once (first encounter), and the second encounter is a
    /// cross-edge (black set), NOT a cycle. C should NOT be IsCycleRef.
    /// </summary>
    [Fact]
    public void CrossEdgeDAG()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:p", "Parent", dbName: "Parent", implicit_: true)
            .AddQuest("quest:a", "Quest A", dbName: "QuestA", implicit_: true)
            .AddQuest("quest:b", "Quest B", dbName: "QuestB", implicit_: true)
            .AddQuest("quest:c", "Quest C", dbName: "QuestC", implicit_: true)
            .AddEdge("quest:p", "quest:a", EdgeType.RequiresQuest)
            .AddEdge("quest:p", "quest:b", EdgeType.RequiresQuest)
            .AddEdge("quest:a", "quest:c", EdgeType.RequiresQuest)
            .AddEdge("quest:b", "quest:c", EdgeType.RequiresQuest);

        var harness = SnapshotHarness.FromGraph(builder);
        var tree = harness.BuildViewTree("quest:p");

        Assert.NotNull(tree);
        Assert.False(tree!.IsCycleRef, "Parent quest should not be infeasible");

        // C should be reachable in the tree and NOT marked as a cycle ref.
        var c = ViewTreeAssert.FindChild(tree, "quest:c");
        Assert.False(c.IsCycleRef, "Quest C is a cross-edge (shared), not a cycle");
    }

    /// <summary>
    /// Item A is CraftedFrom Recipe R, Recipe R RequiresMaterial Item A.
    /// CraftedFrom edges go item → recipe (OutEdge).
    /// RequiresMaterial edges go recipe → item (OutEdge).
    /// The item expansion should detect the cycle when it tries to expand
    /// Item A again from the recipe's material requirement.
    /// Since the recipe's only material is cyclically self-referencing,
    /// the recipe subtree is infeasible, making item:a infeasible,
    /// so it gets pruned from the step children.
    /// </summary>
    [Fact]
    public void ItemSourceCycle()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:root", "Root Quest", dbName: "RootQuest", implicit_: true)
            .AddItem("item:a", "Cyclic Item")
            .AddRecipe("recipe:r", "Self Recipe")
            .AddEdge("quest:root", "item:a", EdgeType.StepRead)
            .AddEdge("item:a", "recipe:r", EdgeType.CraftedFrom)
            .AddEdge("recipe:r", "item:a", EdgeType.RequiresMaterial);

        var harness = SnapshotHarness.FromGraph(builder);
        var tree = harness.BuildViewTree("quest:root");

        Assert.NotNull(tree);
        // Item A's only source is a recipe that requires Item A itself.
        // The recipe material hits the itemVisited cycle check, making the
        // recipe infeasible. With no viable source, item:a is infeasible
        // and pruned from the quest's step children.
        ViewTreeAssert.HasNoChild(tree!, "item:a");
    }

    /// <summary>
    /// A → requires B → requires C → requires A. Three-hop cycle.
    /// Building from A: expanding B expands C, C's RequiresQuest(A) is
    /// a back-edge, making C infeasible. C's infeasibility propagates
    /// to B, then to A.
    /// </summary>
    [Fact]
    public void MultiHopCycle()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:a", "Quest A", dbName: "QuestA", implicit_: true)
            .AddQuest("quest:b", "Quest B", dbName: "QuestB", implicit_: true)
            .AddQuest("quest:c", "Quest C", dbName: "QuestC", implicit_: true)
            .AddEdge("quest:a", "quest:b", EdgeType.RequiresQuest)
            .AddEdge("quest:b", "quest:c", EdgeType.RequiresQuest)
            .AddEdge("quest:c", "quest:a", EdgeType.RequiresQuest);

        var harness = SnapshotHarness.FromGraph(builder);
        var tree = harness.BuildViewTree("quest:a");

        Assert.NotNull(tree);
        Assert.True(tree!.IsCycleRef, "Quest A should be infeasible (3-hop cycle)");
    }

    /// <summary>
    /// Real-world pattern: Quest Q has two step-read items. Item A drops
    /// from Character C (feasible path). Item B's only source is
    /// RewardsItem from Quest Q itself (circular — can't complete Q to
    /// get B when completing Q requires reading B).
    ///
    /// Item B is infeasible (back-edge source pruned, no viable sources
    /// remain) and gets removed from step children. Item A has character:c
    /// as a viable source and remains. The quest overall is feasible.
    /// </summary>
    [Fact]
    public void WylandsNotePattern()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("quest:q", "Wylands Quest", dbName: "WylandsQuest", implicit_: true)
            .AddItem("item:a", "Torn Note")
            .AddItem("item:b", "Marching Orders")
            .AddCharacter("character:c", "Ghost", scene: "Zone1")
            .AddEdge("quest:q", "item:a", EdgeType.StepRead)
            .AddEdge("quest:q", "item:b", EdgeType.StepRead)
            .AddEdge("character:c", "item:a", EdgeType.DropsItem)
            .AddEdge("quest:q", "item:b", EdgeType.RewardsItem)
            .AddEdge("quest:q", "character:c", EdgeType.AssignedBy)
            .AddEdge("quest:q", "character:c", EdgeType.CompletedBy);

        var harness = SnapshotHarness.FromGraph(builder);
        var tree = harness.BuildViewTree("quest:q");

        Assert.NotNull(tree);
        Assert.False(tree!.IsCycleRef, "Quest should be feasible — Item A has a viable source");

        // Item A should have character:c as a viable source.
        var itemA = ViewTreeAssert.FindChild(tree, "item:a");
        Assert.False(itemA.IsCycleRef, "Item A should not be a cycle ref");
        ViewTreeAssert.FindChild(itemA, "character:c");

        // Item B's only source is quest:q (back-edge). With no viable source,
        // item:b is infeasible and pruned from the quest's step children.
        ViewTreeAssert.HasNoChild(tree, "item:b");
    }
}
