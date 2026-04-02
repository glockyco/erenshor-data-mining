using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class NavigationTargetSelectorTests
{
    // ── Helpers ─────────────────────────────────────────────────────────────

    /// <summary>A ZoneRouter built from an empty graph — knows no zones or routes.</summary>
    private static ZoneRouter EmptyRouter() =>
        SnapshotHarness.FromGraph(new TestGraphBuilder()).Router;

    /// <summary>
    /// Builds a minimal <see cref="ResolvedQuestTarget"/> with only the fields that
    /// <see cref="NavigationTargetSelector.SelectBest"/> actually reads:
    /// <c>Scene</c>, <c>X/Y/Z</c>, <c>IsActionable</c>, and <c>Semantic.GoalKind</c>.
    /// All other fields receive stub values.
    /// </summary>
    private static ResolvedQuestTarget MakeTarget(
        string? scene,
        float x = 0f,
        float y = 0f,
        float z = 0f,
        bool isActionable = true,
        NavigationGoalKind goalKind = NavigationGoalKind.StartQuest)
    {
        var stubNode = new Node { Key = "stub", Type = NodeType.Character, DisplayName = "stub" };
        var ctx = new ResolvedNodeContext("stub", stubNode);
        var semantic = new ResolvedActionSemantic(
            goalKind, NavigationTargetKind.Character, ResolvedActionKind.Talk,
            null, null, null, null, "stub", null, null, null, null,
            MarkerType.Objective, 0);
        var explanation = new NavigationExplanation(
            goalKind, NavigationTargetKind.Character, ctx, ctx,
            "stub", "stub", null, null, null);
        return new ResolvedQuestTarget(
            "stub", scene, null, ctx, ctx, semantic, explanation,
            x, y, z, isActionable);
    }

    private const string ZoneA = "ZoneA";
    private const string ZoneB = "ZoneB";
    private const string ZoneC = "ZoneC";

    // Player at origin for all tests unless otherwise specified.
    private const float PX = 0f, PY = 0f, PZ = 0f;

    // ── Tests ────────────────────────────────────────────────────────────────

    [Fact]
    public void SelectBest_EmptyTargets_ReturnsNull()
    {
        var result = NavigationTargetSelector.SelectBest(
            Array.Empty<ResolvedQuestTarget>(), PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.Null(result);
    }

    [Fact]
    public void SelectBest_SameZoneActionableBeatsCloserNonActionable()
    {
        // Non-actionable at 5m; actionable at 20m. Actionable must win despite being farther.
        var targets = new[]
        {
            MakeTarget(ZoneA, x: 5f,  isActionable: false),
            MakeTarget(ZoneA, x: 20f, isActionable: true),
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.True(result!.Value.IsSameZone);
        Assert.Equal(20f, result.Value.Target.X);
    }

    [Fact]
    public void SelectBest_SameZoneBeatesCrossZone()
    {
        // Cross-zone target is near origin; same-zone target is far. Same-zone must still win.
        var targets = new[]
        {
            MakeTarget(ZoneB, x: 1f),   // cross-zone, very close in world-space
            MakeTarget(ZoneA, x: 500f), // same-zone, very far
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.True(result!.Value.IsSameZone);
        Assert.Equal(ZoneA, result.Value.Target.Scene);
    }

    [Fact]
    public void SelectBest_SkipsTravelToZone()
    {
        // Only TravelToZone targets present — all must be skipped → null result.
        var targets = new[]
        {
            MakeTarget(ZoneA, x: 10f, goalKind: NavigationGoalKind.TravelToZone),
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.Null(result);
    }

    [Fact]
    public void SelectBest_TravelToZone_DoesNotBlockOtherTargets()
    {
        // A TravelToZone candidate is in the current zone (it's a zone exit) but must be
        // ignored. The cross-zone objective should still be returned.
        var targets = new[]
        {
            MakeTarget(ZoneA, x: 5f, goalKind: NavigationGoalKind.TravelToZone),
            MakeTarget(ZoneB),
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.False(result!.Value.IsSameZone);
        Assert.Equal(ZoneB, result.Value.Target.Scene);
    }

    [Fact]
    public void SelectBest_CrossZone_PicksFewestHops()
    {
        // Graph: ZoneA → ZoneB (1 hop), ZoneA → ZoneC via ZoneB (2 hops).
        // ZoneC target is at x=100 (closer numerically), ZoneB target at x=200.
        // ZoneB must win because hop count takes priority over world-space distance.
        var graph = new TestGraphBuilder()
            .AddZone("zone:a", "Zone A", scene: ZoneA)
            .AddZone("zone:b", "Zone B", scene: ZoneB)
            .AddZone("zone:c", "Zone C", scene: ZoneC)
            .AddZoneLine("zl:ab", "A→B", scene: ZoneA,
                destinationZoneKey: "zone:b", x: 10, y: 0, z: 0)
            .AddZoneLine("zl:bc", "B→C", scene: ZoneB,
                destinationZoneKey: "zone:c", x: 20, y: 0, z: 0)
            .Build();
        var harness = SnapshotHarness.FromSnapshot(
            graph, new StateSnapshot { CurrentZone = ZoneA });

        var targets = new[]
        {
            MakeTarget(ZoneC, x: 100f), // 2 hops
            MakeTarget(ZoneB, x: 200f), // 1 hop
        };

        var result = NavigationTargetSelector.SelectBest(
            targets, PX, PY, PZ, ZoneA, harness.Router);

        Assert.NotNull(result);
        Assert.False(result!.Value.IsSameZone);
        Assert.Equal(ZoneB, result.Value.Target.Scene);
        Assert.Equal(1, result.Value.HopCount);
    }

    [Fact]
    public void SelectBest_SameZone_ClosestSelected()
    {
        var target = MakeTarget(ZoneA, x: 42f);

        var result = NavigationTargetSelector.SelectBest(
            new[] { target }, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.True(result!.Value.IsSameZone);
        Assert.Equal(42f, result.Value.Target.X, precision: 0);
    }

    [Fact]
    public void SelectBest_HopCount_CrossZone()
    {
        var graph = new TestGraphBuilder()
            .AddZone("zone:a", "Zone A", scene: ZoneA)
            .AddZone("zone:b", "Zone B", scene: ZoneB)
            .AddZoneLine("zl:ab", "A→B", scene: ZoneA,
                destinationZoneKey: "zone:b", x: 10, y: 0, z: 0)
            .Build();
        var harness = SnapshotHarness.FromSnapshot(
            graph, new StateSnapshot { CurrentZone = ZoneA });

        var result = NavigationTargetSelector.SelectBest(
            new[] { MakeTarget(ZoneB) }, PX, PY, PZ, ZoneA, harness.Router);

        Assert.NotNull(result);
        Assert.False(result!.Value.IsSameZone);
        Assert.Equal(1, result.Value.HopCount);
    }

    [Fact]
    public void SelectBest_CrossZone_NoRoute_ReturnsNegativeHopCount()
    {
        // EmptyRouter has no zone lines — no route to ZoneC exists.
        // Target is still returned but HopCount must be -1.
        var result = NavigationTargetSelector.SelectBest(
            new[] { MakeTarget(ZoneC) }, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.False(result!.Value.IsSameZone);
        Assert.Equal(-1, result.Value.HopCount);
    }
}
