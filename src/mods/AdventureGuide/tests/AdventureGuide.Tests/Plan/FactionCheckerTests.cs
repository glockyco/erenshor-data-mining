using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Plan;

public sealed class FactionCheckerTests
{
    [Fact]
    public void StaticHostile_IsAlwaysHostile()
    {
        // IsFriendly=false means statically hostile regardless of faction rep.
        var graph = new TestGraphBuilder()
            .AddNode("character:mob", NodeType.Character, "Mob")
            .Build();

        var node = new Node { Key = "character:mob", Type = NodeType.Character, IsFriendly = false };

        // getFactionValue would return friendly rep, but static flag wins.
        bool result = FactionChecker.IsCurrentlyHostile(node, graph, _ => 100f);

        Assert.True(result);
    }

    [Fact]
    public void FriendlyNoFaction_IsNeverHostile()
    {
        // Purely static friendly NPC with no world faction — never hostile.
        var graph = new TestGraphBuilder()
            .Build();

        var node = new Node { Key = "character:merchant", Type = NodeType.Character, IsFriendly = true, FactionKey = null };

        bool result = FactionChecker.IsCurrentlyHostile(node, graph, _ => null);

        Assert.False(result);
    }

    [Fact]
    public void FriendlyWithNegativeRep_IsHostile()
    {
        // Faction rep < 0 makes the character hostile even if IsFriendly=true.
        var graph = new TestGraphBuilder()
            .AddNode("faction:merchants", NodeType.Faction, "Merchants")
            .Build();

        // Manually set Refname since TestGraphBuilder.AddNode doesn't expose it.
        var factionNode = graph.GetNode("faction:merchants")!;
        factionNode.Refname = "MERCHANTS";

        var node = new Node { Key = "character:merchant", Type = NodeType.Character, IsFriendly = true, FactionKey = "faction:merchants" };

        bool result = FactionChecker.IsCurrentlyHostile(node, graph, refname => refname == "MERCHANTS" ? -50f : null);

        Assert.True(result);
    }

    [Fact]
    public void FriendlyWithPositiveRep_IsNotHostile()
    {
        // Faction rep >= 0 — character remains friendly.
        var graph = new TestGraphBuilder()
            .AddNode("faction:merchants", NodeType.Faction, "Merchants")
            .Build();

        var factionNode = graph.GetNode("faction:merchants")!;
        factionNode.Refname = "MERCHANTS";

        var node = new Node { Key = "character:merchant", Type = NodeType.Character, IsFriendly = true, FactionKey = "faction:merchants" };

        bool result = FactionChecker.IsCurrentlyHostile(node, graph, refname => refname == "MERCHANTS" ? 100f : null);

        Assert.False(result);
    }

    [Fact]
    public void FriendlyWithUnknownFaction_IsNotHostile()
    {
        // Lookup returns null (refname not in GlobalFactionManager) — fail-safe: treat as not hostile.
        var graph = new TestGraphBuilder()
            .AddNode("faction:merchants", NodeType.Faction, "Merchants")
            .Build();

        var factionNode = graph.GetNode("faction:merchants")!;
        factionNode.Refname = "MERCHANTS";

        var node = new Node { Key = "character:merchant", Type = NodeType.Character, IsFriendly = true, FactionKey = "faction:merchants" };

        bool result = FactionChecker.IsCurrentlyHostile(node, graph, _ => null);

        Assert.False(result);
    }
}
