using AdventureGuide.Graph;
using AdventureGuide.Resolution;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class ItemSourceVisibilityPolicyTests
{
    private static readonly VisibilityTestSource Hostile = new(
        "npc:wolf",
        EdgeType.DropsItem,
        true
    );
    private static readonly VisibilityTestSource Friendly = new(
        "npc:farmer",
        EdgeType.DropsItem,
        false
    );
    private static readonly VisibilityTestSource Merchant = new(
        "npc:trader",
        EdgeType.SellsItem,
        false
    );
    private static readonly VisibilityTestSource Giver = new(
        "npc:questgiver",
        EdgeType.GivesItem,
        false
    );

    [Fact]
    public void HostileDrops_SuppressFriendlyDrops()
    {
        var sources = new[] { Hostile, Friendly, Merchant };

        var visible = ItemSourceVisibilityPolicy.Filter(
            sources,
            src => src.EdgeType,
            src => src.IsHostile
        );

        Assert.Contains(Hostile, visible);
        Assert.DoesNotContain(Friendly, visible);
        Assert.Contains(Merchant, visible);
    }

    [Fact]
    public void NoHostileDrops_KeepsAllSources()
    {
        var sources = new[] { Friendly, Merchant, Giver };

        var visible = ItemSourceVisibilityPolicy.Filter(
            sources,
            src => src.EdgeType,
            src => src.IsHostile
        );

        Assert.Equal(sources, visible);
    }

    [Fact]
    public void NonDropSources_NeverSuppressed()
    {
        var sources = new[] { Hostile, Merchant, Giver };

        var visible = ItemSourceVisibilityPolicy.Filter(
            sources,
            src => src.EdgeType,
            src => src.IsHostile
        );

        Assert.Contains(Merchant, visible);
        Assert.Contains(Giver, visible);
    }

    private readonly record struct VisibilityTestSource(string Key, EdgeType EdgeType, bool IsHostile);
}
