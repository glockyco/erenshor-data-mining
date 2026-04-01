using AdventureGuide.Graph;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

/// <summary>
/// Tests that infeasibility cascades correctly through the view tree:
/// when leaf sources are unreachable or cyclic, their parent nodes
/// are pruned or marked infeasible according to AND/OR semantics.
/// </summary>
public class InfeasibilityCascadeTests
{
    /// <summary>
    /// An item required by a quest has no acquisition sources at all (no drops,
    /// vendors, crafts, etc.) and the player doesn't have it in inventory.
    /// The item should be built as IsCycleRef (infeasible) since it has zero
    /// children and IsSatisfied is false.
    /// </summary>
    [Fact]
    public void ItemWithAllSourcesPruned_IsInfeasible()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("q", "Test Quest", dbName: "TestQuest")
            .AddItem("i", "Unobtainable Item")
            .AddCharacter("npc", "Quest Giver")
            // Quest structure: NPC assigns and completes, item is a required item.
            .AddEdge("q", "npc", EdgeType.AssignedBy)
            .AddEdge("q", "npc", EdgeType.CompletedBy)
            .AddEdge("q", "i", EdgeType.RequiresItem);
            // item:i has NO incoming DropsItem/SellsItem/GivesItem/YieldsItem/RewardsItem
            // and no CraftedFrom edges. Inventory is empty.

        var harness = SnapshotHarness.FromGraph(builder);
        var tree = harness.BuildViewTree("q");

        Assert.NotNull(tree);
        // Item with no sources and not in inventory → infeasible → IsCycleRef.
        // RequiresItem children are added directly (not skipped on cycle ref),
        // so it should appear as a cycle ref child.
        ViewTreeAssert.ChildIsCycleRef(tree!, "i");
    }

    /// <summary>
    /// An item has two drop sources: Character A (infeasible because it creates
    /// a quest cycle) and Character B (straightforward, reachable).
    /// After pruning A, B remains — the item should survive with B as a child.
    /// </summary>
    [Fact]
    public void ItemWithOneSourceRemaining_Survives()
    {
        // Character A is behind an infeasible prerequisite quest that creates a cycle.
        // Character B is a plain character with no blockers.
        var builder = new TestGraphBuilder()
            .AddQuest("q", "Main Quest", dbName: "MainQuest")
            .AddItem("i", "Dropped Item")
            .AddCharacter("char_a", "Blocked Dropper")
            .AddCharacter("char_b", "Easy Dropper")
            .AddQuest("prereq", "Prereq Quest", dbName: "PrereqQuest")
            // Main quest requires the item.
            .AddEdge("q", "i", EdgeType.RequiresItem)
            .AddEdge("q", "char_b", EdgeType.AssignedBy)
            .AddEdge("q", "char_b", EdgeType.CompletedBy)
            // Both characters drop the item.
            .AddEdge("char_a", "i", EdgeType.DropsItem)
            .AddEdge("char_b", "i", EdgeType.DropsItem)
            // Character A requires completing a prerequisite quest that itself
            // requires completing the main quest — mutual cycle makes A infeasible.
            // Actually, character unlock is not gated this way. The item source
            // expansion uses AddIncomingSources which calls BuildLeafOrExpand on
            // each source character. Characters are leaves (not quests), so they
            // won't become cycle refs unless they have an infeasible unlock dep.
            //
            // Instead: character A requires a quest unlock that is infeasible.
            // We can make prereq quest require main quest (cycle).
            // Then add UnlocksCharacter from prereq → char_a.
            .AddEdge("prereq", "char_a", EdgeType.UnlocksCharacter)
            .AddEdge("prereq", "q", EdgeType.RequiresQuest)
            // prereq needs an assigner to not be auto-infeasible.
            .AddEdge("prereq", "char_b", EdgeType.AssignedBy)
            .AddEdge("prereq", "char_b", EdgeType.CompletedBy);

        var harness = SnapshotHarness.FromGraph(builder);
        var tree = harness.BuildViewTree("q");

        Assert.NotNull(tree);
        // Item should be in the tree (not pruned) because char_b provides a viable source.
        var itemNode = ViewTreeAssert.FindChild(tree!, "i");
        Assert.False(itemNode.IsCycleRef, "Item should not be infeasible with a viable source");
        // char_b should be present as a source.
        ViewTreeAssert.FindChild(itemNode, "char_b");
    }

    /// <summary>
    /// A recipe requires two materials (AND semantics). Material M1 has a source
    /// (character drops it). Material M2 has no sources and is not in inventory.
    /// Since M2 is infeasible, the recipe is infeasible — it should be pruned
    /// from the product item's children.
    /// </summary>
    [Fact]
    public void RecipeWithInfeasibleIngredient_IsInfeasible()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("q", "Craft Quest", dbName: "CraftQuest")
            .AddItem("product", "Crafted Product")
            .AddRecipe("recipe", "Craft Recipe")
            .AddItem("m1", "Material One")
            .AddItem("m2", "Material Two (Unobtainable)")
            .AddCharacter("npc", "Quest Giver")
            .AddCharacter("mat_dropper", "Material Dropper")
            // Quest structure.
            .AddEdge("q", "npc", EdgeType.AssignedBy)
            .AddEdge("q", "npc", EdgeType.CompletedBy)
            .AddEdge("q", "product", EdgeType.RequiresItem)
            // Product is crafted from recipe, recipe needs two materials.
            .AddEdge("product", "recipe", EdgeType.CraftedFrom)
            .AddEdge("recipe", "m1", EdgeType.RequiresMaterial)
            .AddEdge("recipe", "m2", EdgeType.RequiresMaterial)
            // M1 has a source, M2 has none.
            .AddEdge("mat_dropper", "m1", EdgeType.DropsItem);

        var harness = SnapshotHarness.FromGraph(builder);
        var tree = harness.BuildViewTree("q");

        Assert.NotNull(tree);
        // The product item: its only source (recipe) is infeasible because m2
        // has no sources. With no viable children and not in inventory, the
        // product itself is infeasible.
        ViewTreeAssert.ChildIsCycleRef(tree!, "product");
    }

    /// <summary>
    /// Quest Q requires prerequisite Quest P. Quest P requires Q back (mutual
    /// cycle). P is built as a back-edge cycle ref. IsQuestInfeasible Rule 3
    /// fires: RequiresQuest child is cycle ref AND on-path → Q is infeasible.
    /// Since Q is the root quest, it should be returned as infeasible (IsCycleRef).
    /// </summary>
    [Fact]
    public void QuestPrereqMutualCycle_BothInfeasible()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("q", "Quest Q", dbName: "QuestQ")
            .AddQuest("p", "Quest P", dbName: "QuestP")
            .AddCharacter("npc", "Quest Giver")
            // Both quests have a valid assigner (NPC) so they don't fail Rule 1.
            .AddEdge("q", "npc", EdgeType.AssignedBy)
            .AddEdge("q", "npc", EdgeType.CompletedBy)
            .AddEdge("p", "npc", EdgeType.AssignedBy)
            .AddEdge("p", "npc", EdgeType.CompletedBy)
            // Mutual prerequisite cycle.
            .AddEdge("q", "p", EdgeType.RequiresQuest)
            .AddEdge("p", "q", EdgeType.RequiresQuest);

        var harness = SnapshotHarness.FromGraph(builder);
        var tree = harness.BuildViewTree("q");

        // Q is the root. Building Q puts it on the path.
        // Q expands P (RequiresQuest). P's expansion finds Q on-path → Q ref is cycle ref.
        // IsQuestInfeasible(P) Rule 3: RequiresQuest child Q is cycle ref AND on-path → P is infeasible.
        // P gets added to _questsInfeasible, returns as IsCycleRef.
        // Then IsQuestInfeasible(Q) Rule 3: RequiresQuest child P is cycle ref
        // AND _questsInfeasible.Contains(P) → Q is infeasible.
        // Build returns IsCycleRef node for Q.
        Assert.NotNull(tree);
        Assert.True(tree!.IsCycleRef,
            "Root quest with mutual prerequisite cycle should be infeasible");
    }

    /// <summary>
    /// Quest Q requires prereq Quest P. P is infeasible because it has
    /// AssignedBy edges but all assigners are behind infeasible unlock
    /// dependencies (the character's unlock quest requires completing P first,
    /// creating a cycle). Rule 1 fires for P, making it infeasible, which
    /// cascades via Rule 3 to make Q infeasible.
    /// </summary>
    [Fact]
    public void QuestPrereqInfeasibleAssigner_CascadesToParent()
    {
        var builder = new TestGraphBuilder()
            .AddQuest("q", "Main Quest", dbName: "MainQuest")
            .AddQuest("p", "Prereq Quest", dbName: "PrereqQuest")
            .AddCharacter("npc_q", "Main Giver")
            .AddCharacter("npc_p", "Locked Giver")
            // Main quest is well-formed.
            .AddEdge("q", "npc_q", EdgeType.AssignedBy)
            .AddEdge("q", "npc_q", EdgeType.CompletedBy)
            .AddEdge("q", "p", EdgeType.RequiresQuest)
            // Prereq P is assigned by npc_p.
            .AddEdge("p", "npc_p", EdgeType.AssignedBy)
            .AddEdge("p", "npc_p", EdgeType.CompletedBy)
            // npc_p is unlocked by completing P itself — cycle.
            .AddEdge("p", "npc_p", EdgeType.UnlocksCharacter);

        var harness = SnapshotHarness.FromGraph(builder);
        var tree = harness.BuildViewTree("q");

        Assert.NotNull(tree);
        // P's assigner npc_p has an unlock dependency (quest P) which is the
        // quest currently being built → back-edge cycle → unlock is infeasible
        // → npc_p returned as IsCycleRef → AddEdgeChildren skips it →
        // P has no valid AssignedBy children → Rule 1 → P infeasible.
        // Then Q's Rule 3: RequiresQuest P is in _questsInfeasible → Q infeasible.
        Assert.True(tree!.IsCycleRef,
            "Quest whose prereq has an infeasible assigner should cascade to infeasible");
    }
}
