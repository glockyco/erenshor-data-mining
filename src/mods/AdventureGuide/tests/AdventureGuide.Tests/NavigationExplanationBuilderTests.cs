using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

/// <summary>
/// Unit tests for <see cref="NavigationExplanationBuilder"/> arrow primary text.
/// Covers verbs that were historically inconsistent across surfaces.
/// </summary>
public sealed class NavigationExplanationBuilderTests
{
    // ── helpers ──────────────────────────────────────────────────────────────

    private static ResolvedNodeContext Ctx(string key, NodeType type, string name,
        EdgeType? edgeType = null, int? quantity = null)
    {
        var node = new Node { Key = key, Type = type, DisplayName = name };
        return new ResolvedNodeContext(key, node, edgeType, quantity);
    }

    private static NavigationExplanation Arrow(
        ResolvedActionKind actionKind,
        string targetName,
        string? keywordText = null,
        NavigationGoalKind goalKind = NavigationGoalKind.Generic,
        int? targetQuantity = null)
    {
        var stub = new Node { Key = "goal", Type = NodeType.Item, DisplayName = "goal" };
        var goalCtx   = new ResolvedNodeContext("goal", stub);
        var targetCtx = Ctx("target", NodeType.Character, targetName,
            quantity: targetQuantity);

        var semantic = new ResolvedActionSemantic(
            goalKind, NavigationTargetKind.Character, actionKind,
            goalNodeKey: null, goalQuantity: null,
            keywordText, payloadText: null, targetName,
            contextText: null, rationaleText: null,
            zoneText: null, availabilityText: null,
            QuestMarkerKind.Objective, markerPriority: 20);

        return NavigationExplanationBuilder.Build(semantic, goalCtx, targetCtx);
    }

    // ── Fish ─────────────────────────────────────────────────────────────────

    [Fact]
    public void ArrowPrimary_Fish_HasFishAtVerb()
    {
        var result = Arrow(ResolvedActionKind.Fish, "Silverfin Lake");
        Assert.Equal("Fish at Silverfin Lake", result.PrimaryText);
    }

    [Fact]
    public void ArrowPrimary_Fish_NotBareTargetName()
    {
        // Regression: was previously just "Silverfin Lake" with no verb.
        var result = Arrow(ResolvedActionKind.Fish, "Silverfin Lake");
        Assert.NotEqual("Silverfin Lake", result.PrimaryText);
    }

    // ── Collect ──────────────────────────────────────────────────────────────

    [Fact]
    public void ArrowPrimary_Collect_HasCollectVerb()
    {
        var result = Arrow(ResolvedActionKind.Collect, "Rusty Item Bag");
        Assert.Equal("Collect Rusty Item Bag", result.PrimaryText);
    }

    [Fact]
    public void ArrowPrimary_Collect_NotBareTargetName()
    {
        // Regression: was previously just "Rusty Item Bag" with no verb.
        var result = Arrow(ResolvedActionKind.Collect, "Rusty Item Bag");
        Assert.NotEqual("Rusty Item Bag", result.PrimaryText);
    }

    // ── Travel ───────────────────────────────────────────────────────────────

    [Fact]
    public void ArrowPrimary_Travel_UsesTravelToNotGoTo()
    {
        var result = Arrow(ResolvedActionKind.Travel, "Stowaway's Step");
        Assert.Equal("Travel to Stowaway's Step", result.PrimaryText);
        Assert.DoesNotContain("Go to", result.PrimaryText);
    }

    // ── Existing verbs unchanged ──────────────────────────────────────────────

    [Fact]
    public void ArrowPrimary_Mine_HasMineVerb()
    {
        var result = Arrow(ResolvedActionKind.Mine, "Mineral Deposit");
        Assert.Equal("Mine Mineral Deposit", result.PrimaryText);
    }

    [Fact]
    public void ArrowPrimary_Kill_HasKillVerb()
    {
        var result = Arrow(ResolvedActionKind.Kill, "Spark Beetle");
        Assert.Equal("Kill Spark Beetle", result.PrimaryText);
    }

    [Fact]
    public void ArrowPrimary_Kill_WithQuantity_ShowsCount()
    {
        var result = Arrow(ResolvedActionKind.Kill, "Spark Beetle", targetQuantity: 3);
        Assert.Equal("Kill Spark Beetle (3)", result.PrimaryText);
    }
}
