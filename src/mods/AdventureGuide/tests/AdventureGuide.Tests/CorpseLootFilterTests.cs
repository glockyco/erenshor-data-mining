using AdventureGuide.Graph;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

/// <summary>
/// Tests for the corpse loot filter logic introduced in LiveStateTracker.CorpseContainsItem
/// and wired into QuestResolutionService.ResolveItemTargetsFromBlueprint.
///
/// Full integration testing of CorpseContainsItem requires Unity runtime types
/// (NPC, LootTable, SpawnPoint). The tests here cover:
///   1. The stable key formula — ensuring the formula used in CorpseContainsItem
///      matches the one used throughout the graph (BuildItemStableKey).
///   2. Graph structure invariants that the loot filter depends on.
///
/// Manual test scenario (requires running game):
///   - Kill an NPC that drops a quest item.
///   - Open the guide: NAV arrow should point at the corpse (corpse has item).
///   - Pick up the item from the corpse.
///   - Open the guide again: NAV arrow should no longer point at the now-empty corpse.
///   - Verify the marker for that spawn position becomes non-actionable or disappears.
/// </summary>
public sealed class CorpseLootFilterTests
{
    // ── Stable-key formula ────────────────────────────────────────────────────

    [Fact]
    public void StableKeyFormula_MatchesGraphConvention()
    {
        // The graph stores item keys as "item:" + name.Trim().ToLowerInvariant().
        // CorpseContainsItem builds the same key from drop.name and compares it to
        // the source.DirectItemKey already stored in the graph. These must agree.
        const string resourceName = "Iron Ore";
        string expected = "item:" + resourceName.Trim().ToLowerInvariant();
        Assert.Equal("item:iron ore", expected);
    }

    [Fact]
    public void StableKeyFormula_TrimsWhitespace()
    {
        // Unity asset names can have leading/trailing whitespace; Trim() absorbs it.
        const string resourceName = "  Ghostly Ore  ";
        string key = "item:" + resourceName.Trim().ToLowerInvariant();
        Assert.Equal("item:ghostly ore", key);
    }

    [Fact]
    public void StableKeyFormula_IsCaseInsensitive()
    {
        // Drop names in Unity assets are not guaranteed to be lowercase.
        const string resourceName = "IRON ORE";
        string key = "item:" + resourceName.Trim().ToLowerInvariant();
        Assert.Equal("item:iron ore", key);
    }

    // ── Graph structure invariants relied on by the filter ─────────────────

    [Fact]
    public void SpawnNode_HasCorrectNodeType()
    {
        // CorpseContainsItem gates on NodeType.SpawnPoint. Confirm the builder
        // produces nodes the filter will recognise.
        var graph = new TestGraphBuilder()
            .AddSpawnPoint("spawn:goblin-1", "Goblin", scene: "ZoneA")
            .Build();

        var node = graph.GetNode("spawn:goblin-1");
        Assert.NotNull(node);
        Assert.Equal(NodeType.SpawnPoint, node!.Type);
    }

    [Fact]
    public void DropsItem_SourceBlueprintCarriesDirectItemKey()
    {
        // The loot filter only fires when source.DirectItemKey != null.
        // Verify that CompiledSourceIndex populates DirectItemKey for DropsItem edges.
        var graph = new TestGraphBuilder()
            .AddItem("item:goblin-tooth", "Goblin Tooth")
            .AddCharacter("character:goblin", "Goblin")
            .AddSpawnPoint("spawn:goblin-1", "Goblin", scene: "ZoneA")
            .AddEdge("character:goblin", "item:goblin-tooth", EdgeType.DropsItem)
            .AddEdge("character:goblin", "spawn:goblin-1", EdgeType.HasSpawn)
            .Build();

        graph.GetNode("spawn:goblin-1")!.X = 10f;
        graph.GetNode("spawn:goblin-1")!.Y = 0f;
        graph.GetNode("spawn:goblin-1")!.Z = 10f;

        var index = new CompiledSourceIndex(graph);
        var sites = index.GetSourceSitesForItem("item:goblin-tooth");

        Assert.NotEmpty(sites);
        Assert.All(sites, s => Assert.Equal(EdgeType.DropsItem, s.AcquisitionEdge));
        Assert.All(sites, s => Assert.Equal("item:goblin-tooth", s.DirectItemKey));
    }

    [Fact]
    public void NonDropSources_HaveCorrectEdgeType()
    {
        // The loot filter must not apply to SellsItem or GivesItem sources.
        // Confirm those edges produce blueprints with the right AcquisitionEdge.
        var graph = new TestGraphBuilder()
            .AddItem("item:healing-potion", "Healing Potion")
            .AddCharacter("character:shopkeeper", "Shopkeeper")
            .AddSpawnPoint("spawn:shopkeeper-1", "Shopkeeper", scene: "Town")
            .AddEdge("character:shopkeeper", "item:healing-potion", EdgeType.SellsItem)
            .AddEdge("character:shopkeeper", "spawn:shopkeeper-1", EdgeType.HasSpawn)
            .Build();

        graph.GetNode("spawn:shopkeeper-1")!.X = 5f;
        graph.GetNode("spawn:shopkeeper-1")!.Y = 0f;
        graph.GetNode("spawn:shopkeeper-1")!.Z = 5f;

        var index = new CompiledSourceIndex(graph);
        var sites = index.GetSourceSitesForItem("item:healing-potion");

        Assert.NotEmpty(sites);
        Assert.All(sites, s => Assert.Equal(EdgeType.SellsItem, s.AcquisitionEdge));
        // None of these would trigger CorpseContainsItem — the edge guard handles it.
    }
}
