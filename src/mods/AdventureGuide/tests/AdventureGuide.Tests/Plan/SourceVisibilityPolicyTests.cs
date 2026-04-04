using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Plan;

public sealed class SourceVisibilityPolicyTests
{
    // Helper: build a SourceSiteBlueprint for a character with the given edge type.
    private static SourceSiteBlueprint Blueprint(string sourceKey, EdgeType edge, string itemKey = "item:x")
        => new(sourceKey, NodeType.Character, edge, scene: null, directItemKey: itemKey,
               staticPositions: Array.Empty<StaticSourcePosition>());

    // Helper: build a graph containing named characters with IsFriendly flags.
    private static (EntityGraph graph, SourceVisibilityPolicy policy) MakePolicy(
        (string key, bool isFriendly)[] characters,
        Func<string, float?>? factionLookup = null)
    {
        var builder = new TestGraphBuilder();
        foreach (var (key, _) in characters)
            builder.AddCharacter(key, key);

        var graph = builder.Build();

        // Patch IsFriendly after construction (graph nodes are mutable).
        foreach (var (key, isFriendly) in characters)
            graph.GetNode(key)!.IsFriendly = isFriendly;

        var policy = new SourceVisibilityPolicy(graph, factionLookup ?? (_ => null));
        return (graph, policy);
    }

    [Fact]
    public void FilterBlueprints_NoHostileDrop_ReturnsSourcesUnchanged()
    {
        // All characters are friendly — no hostile drop exists.
        var (_, policy) = MakePolicy(new[]
        {
            ("character:friendly-a", true),
            ("character:friendly-b", true),
        });

        var sources = new[]
        {
            Blueprint("character:friendly-a", EdgeType.DropsItem),
            Blueprint("character:friendly-b", EdgeType.DropsItem),
        };

        var result = policy.FilterBlueprints(sources);

        // No hostile drop → sources returned unchanged (same reference).
        Assert.Same(sources, result);
    }

    [Fact]
    public void FilterBlueprints_HostileDropExists_SuppressesFriendlyDrops()
    {
        var (_, policy) = MakePolicy(new[]
        {
            ("character:hostile", false),  // IsFriendly=false → always hostile
            ("character:friendly", true),
        });

        var sources = new[]
        {
            Blueprint("character:hostile",  EdgeType.DropsItem),
            Blueprint("character:friendly", EdgeType.DropsItem),
        };

        var result = policy.FilterBlueprints(sources);

        Assert.Single(result);
        Assert.Equal("character:hostile", result[0].SourceNodeKey);
    }

    [Fact]
    public void FilterBlueprints_HostileDropExists_PreservesNonDropSources()
    {
        // A vendor (SellsItem) must always survive even when hostile drops exist.
        var (_, policy) = MakePolicy(new[]
        {
            ("character:hostile", false),
            ("character:friendly", true),
            ("character:vendor", true),
        });

        var sources = new[]
        {
            Blueprint("character:hostile",  EdgeType.DropsItem),
            Blueprint("character:friendly", EdgeType.DropsItem),
            Blueprint("character:vendor",   EdgeType.SellsItem),
        };

        var result = policy.FilterBlueprints(sources);

        Assert.Equal(2, result.Count);
        Assert.Contains(result, s => s.SourceNodeKey == "character:hostile");
        Assert.Contains(result, s => s.SourceNodeKey == "character:vendor");
    }

    [Fact]
    public void FilterBlueprints_UnknownSourceNode_IsKeptFailOpen()
    {
        // A blueprint whose node key is not in the graph must be kept.
        var (_, policy) = MakePolicy(new[]
        {
            ("character:hostile", false),
        });

        var sources = new[]
        {
            Blueprint("character:hostile",     EdgeType.DropsItem),
            Blueprint("character:nonexistent", EdgeType.DropsItem), // not in graph
        };

        var result = policy.FilterBlueprints(sources);

        // Both hostile node and unknown node are kept (fail-open).
        Assert.Equal(2, result.Count);
    }

    [Fact]
    public void FilterBlueprints_AllDropsHostile_ReturnsAll()
    {
        var (_, policy) = MakePolicy(new[]
        {
            ("character:hostile-a", false),
            ("character:hostile-b", false),
        });

        var sources = new[]
        {
            Blueprint("character:hostile-a", EdgeType.DropsItem),
            Blueprint("character:hostile-b", EdgeType.DropsItem),
        };

        var result = policy.FilterBlueprints(sources);

        Assert.Equal(2, result.Count);
    }

    [Fact]
    public void IsHostileDropSource_NullNode_ReturnsFalse()
    {
        var (_, policy) = MakePolicy(Array.Empty<(string, bool)>());

        Assert.False(policy.IsHostileDropSource(null));
    }

    [Fact]
    public void IsHostileDropSource_StaticHostile_ReturnsTrue()
    {
        var (graph, policy) = MakePolicy(new[] { ("character:mob", false) });

        Assert.True(policy.IsHostileDropSource(graph.GetNode("character:mob")));
    }

    [Fact]
    public void IsHostileDropSource_FriendlyWithNegativeRep_ReturnsTrue()
    {
        // Faction rep < 0 makes a friendly character hostile at runtime.
        var builder = new TestGraphBuilder()
            .AddCharacter("character:merchant", "Merchant")
            .AddNode("faction:merchants", NodeType.Faction, "Merchants");

        var graph = builder.Build();
        graph.GetNode("character:merchant")!.IsFriendly = true;
        graph.GetNode("character:merchant")!.FactionKey = "faction:merchants";
        graph.GetNode("faction:merchants")!.Refname = "MERCHANTS";

        var policy = new SourceVisibilityPolicy(
            graph, refname => refname == "MERCHANTS" ? -50f : null);

        Assert.True(policy.IsHostileDropSource(graph.GetNode("character:merchant")));
    }
}
