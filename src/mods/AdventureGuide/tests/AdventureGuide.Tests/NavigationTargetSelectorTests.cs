using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Plan;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class NavigationTargetSelectorTests
{
    // -- Helpers -----------------------------------------------------------------

    /// <summary>A ZoneRouter built from an empty guide -- knows no zones or routes.</summary>
    private static ZoneRouter EmptyRouter() =>
        SnapshotHarness.FromBuilder(new CompiledGuideBuilder()).Router;

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
        NavigationGoalKind goalKind = NavigationGoalKind.StartQuest,
        string targetNodeKey = "stub",
        string? sourceKey = null,
        string? requiredForQuestKey = null,
        bool isBlockedPath = false,
        bool isGuaranteedLoot = false,
        NodeType targetNodeType = NodeType.Character
    )
    {
        var stubNode = new Node
        {
            Key = targetNodeKey,
            Type = targetNodeType,
            DisplayName = targetNodeKey,
        };
        var ctx = new ResolvedNodeContext(targetNodeKey, stubNode);
        var semantic = new ResolvedActionSemantic(
            goalKind,
            NavigationTargetKind.Character,
            ResolvedActionKind.Talk,
            null,
            null,
            null,
            null,
            targetNodeKey,
            null,
            null,
            null,
            null,
            QuestMarkerKind.Objective,
            0
        );
        var explanation = new NavigationExplanation(
            goalKind,
            NavigationTargetKind.Character,
            ctx,
            ctx,
            targetNodeKey,
            targetNodeKey,
            null,
            null,
            null
        );
        return new ResolvedQuestTarget(
            targetNodeKey,
            scene,
            sourceKey ?? targetNodeKey,
            ctx,
            ctx,
            semantic,
            explanation,
            x,
            y,
            z,
            isActionable,
            requiredForQuestKey: requiredForQuestKey,
            isBlockedPath: isBlockedPath,
            isGuaranteedLoot: isGuaranteedLoot
        );
    }

    private const string ZoneA = "ZoneA";
    private const string ZoneB = "ZoneB";
    private const string ZoneC = "ZoneC";

    // Player at origin for all tests unless otherwise specified.
    private const float PX = 0f,
        PY = 0f,
        PZ = 0f;

    // -- Tests -------------------------------------------------------------------

    [Fact]
    public void SelectBest_EmptyTargets_ReturnsNull()
    {
        var result = NavigationTargetSelector.SelectBest(
            Array.Empty<ResolvedQuestTarget>(),
            PX,
            PY,
            PZ,
            ZoneA,
            EmptyRouter()
        );

        Assert.Null(result);
    }

    [Fact]
    public void SelectBest_SameZoneActionableBeatsCloserNonActionable()
    {
        // Non-actionable at 5m; actionable at 20m. Actionable must win despite being farther.
        var targets = new[]
        {
            MakeTarget(ZoneA, x: 5f, isActionable: false),
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
            MakeTarget(ZoneB, x: 1f), // cross-zone, very close in world-space
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
        // Only TravelToZone targets present -- all must be skipped -> null result.
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
        // Graph: ZoneA -> ZoneB (1 hop), ZoneA -> ZoneC via ZoneB (2 hops).
        // ZoneC target is at x=100 (closer numerically), ZoneB target at x=200.
        // ZoneB must win because hop count takes priority over world-space distance.
        var guide = new CompiledGuideBuilder()
            .AddZone("zone:a", scene: ZoneA)
            .AddZone("zone:b", scene: ZoneB)
            .AddZone("zone:c", scene: ZoneC)
            .AddZoneLine("zl:ab", scene: ZoneA, destinationZoneKey: "zone:b", x: 10, y: 0, z: 0)
            .AddZoneLine("zl:bc", scene: ZoneB, destinationZoneKey: "zone:c", x: 20, y: 0, z: 0)
            .Build();
        var harness = SnapshotHarness.FromSnapshot(
            guide,
            new StateSnapshot { CurrentZone = ZoneA }
        );

        var targets = new[]
        {
            MakeTarget(ZoneC, x: 100f), // 2 hops
            MakeTarget(ZoneB, x: 200f), // 1 hop
        };

        var result = NavigationTargetSelector.SelectBest(
            targets,
            PX,
            PY,
            PZ,
            ZoneA,
            harness.Router
        );

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
            new[] { target },
            PX,
            PY,
            PZ,
            ZoneA,
            EmptyRouter()
        );

        Assert.NotNull(result);
        Assert.True(result!.Value.IsSameZone);
        Assert.Equal(42f, result.Value.Target.X, precision: 0);
    }

    [Fact]
    public void SelectBest_HopCount_CrossZone()
    {
        var guide = new CompiledGuideBuilder()
            .AddZone("zone:a", scene: ZoneA)
            .AddZone("zone:b", scene: ZoneB)
            .AddZoneLine("zl:ab", scene: ZoneA, destinationZoneKey: "zone:b", x: 10, y: 0, z: 0)
            .Build();
        var harness = SnapshotHarness.FromSnapshot(
            guide,
            new StateSnapshot { CurrentZone = ZoneA }
        );

        var result = NavigationTargetSelector.SelectBest(
            new[] { MakeTarget(ZoneB) },
            PX,
            PY,
            PZ,
            ZoneA,
            harness.Router
        );

        Assert.NotNull(result);
        Assert.False(result!.Value.IsSameZone);
        Assert.Equal(1, result.Value.HopCount);
    }

    [Fact]
    public void SelectBest_CrossZone_NoRoute_ReturnsNegativeHopCount()
    {
        // EmptyRouter has no zone lines -- no route to ZoneC exists.
        // Target is still returned but HopCount must be -1.
        var result = NavigationTargetSelector.SelectBest(
            new[] { MakeTarget(ZoneC) },
            PX,
            PY,
            PZ,
            ZoneA,
            EmptyRouter()
        );

        Assert.NotNull(result);
        Assert.False(result!.Value.IsSameZone);
        Assert.Equal(-1, result.Value.HopCount);
    }

    [Fact]
    public void SelectBest_CrossZone_ManyTargetsSameDestination_SingleHopLookup()
    {
        // 500 cross-zone targets all in ZoneB -- should produce one representative,
        // not 500 FindRoute calls. Verifiable by result being correct and fast.
        var guide = new CompiledGuideBuilder()
            .AddZone("zone:a", scene: ZoneA)
            .AddZone("zone:b", scene: ZoneB)
            .AddZoneLine("zl:ab", scene: ZoneA, destinationZoneKey: "zone:b", x: 10, y: 0, z: 0)
            .Build();
        var harness = SnapshotHarness.FromSnapshot(
            guide,
            new StateSnapshot { CurrentZone = ZoneA }
        );

        var targets = Enumerable.Range(0, 500).Select(i => MakeTarget(ZoneB, x: i)).ToArray();

        var result = NavigationTargetSelector.SelectBest(
            targets,
            PX,
            PY,
            PZ,
            ZoneA,
            harness.Router
        );

        // Correct winner: first target in ZoneB, 1 hop away.
        Assert.NotNull(result);
        Assert.False(result!.Value.IsSameZone);
        Assert.Equal(1, result.Value.HopCount);
        Assert.Equal(ZoneB, result.Value.Target.Scene);
    }

    [Fact]
    public void SelectBest_CrossZone_CloserZoneWins_DespiteMoreTargetsInFarZone()
    {
        // ZoneB is 1 hop, ZoneC is 2 hops. Many targets in ZoneC, one in ZoneB.
        // ZoneB target should still win because fewer hops matter more than count.
        var guide = new CompiledGuideBuilder()
            .AddZone("zone:a", scene: ZoneA)
            .AddZone("zone:b", scene: ZoneB)
            .AddZone("zone:c", scene: ZoneC)
            .AddZoneLine("zl:ab", scene: ZoneA, destinationZoneKey: "zone:b", x: 10, y: 0, z: 0)
            .AddZoneLine("zl:bc", scene: ZoneB, destinationZoneKey: "zone:c", x: 20, y: 0, z: 0)
            .Build();
        var harness = SnapshotHarness.FromSnapshot(
            guide,
            new StateSnapshot { CurrentZone = ZoneA }
        );

        var targets = new[] { MakeTarget(ZoneB) }
            .Concat(Enumerable.Range(0, 100).Select(i => MakeTarget(ZoneC, x: i)))
            .ToArray();

        var result = NavigationTargetSelector.SelectBest(
            targets,
            PX,
            PY,
            PZ,
            ZoneA,
            harness.Router
        );

        Assert.NotNull(result);
        Assert.False(result!.Value.IsSameZone);
        Assert.Equal(1, result.Value.HopCount);
        Assert.Equal(ZoneB, result.Value.Target.Scene);
    }

    [Fact]
    public void Tick_UsesNavigationTargetResolverForQuestKeys()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver", scene: ZoneA, x: 10f, y: 20f, z: 30f)
            .AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "char:giver" })
            .Build();
        var harness = SnapshotHarness.FromSnapshot(
            guide,
            new StateSnapshot { CurrentZone = ZoneA }
        );

        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var unlocks = new UnlockPredicateEvaluator(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            unlocks,
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var navigationResolver = new NavigationTargetResolver(
            guide,
            frontier,
            sourceResolver,
            harness.Router,
            TestPositionResolvers.Create(guide)
        );

        var selector = new NavigationTargetSelector(
            (nodeKey, scene) => navigationResolver.Resolve(nodeKey, scene),
            harness.Router
        );

        selector.Tick(0, 0, 0, ZoneA, new[] { "quest:a" }, force: true);

        Assert.True(selector.TryGet("quest:a", out var selected));
        Assert.Equal("char:giver", selected.Target.TargetNodeKey);
        Assert.Equal(10f, selected.Target.X);
        Assert.Equal(20f, selected.Target.Y);
        Assert.Equal(30f, selected.Target.Z);
    }

    // -- Tick-level regression tests ------------------------------------------------

    [Fact]
    public void Tick_SameZone_PlayerMoves_ReroutesToCloserTarget()
    {
        // Two same-zone nodes: A at x=10, B at x=100.
        // After a force tick with the player at origin, A is closer (D=10 < D=100).
        // A non-force tick with the player at x=150 should reroute to B (D=50 < D=140).
        var nodeA = MakeTarget(ZoneA, x: 10f, targetNodeKey: "node:a");
        var nodeB = MakeTarget(ZoneA, x: 100f, targetNodeKey: "node:b");
        var targets = new[] { nodeA, nodeB };

        var selector = new NavigationTargetSelector(
            (key, _) =>
                key == "quest:test"
                    ? (IReadOnlyList<ResolvedQuestTarget>)targets
                    : Array.Empty<ResolvedQuestTarget>(),
            EmptyRouter()
        );

        // Force tick near A.
        selector.Tick(0, 0, 0, ZoneA, new[] { "quest:test" }, force: true);
        Assert.True(selector.TryGet("quest:test", out var first));
        Assert.Equal("node:a", first.Target.TargetNodeKey);

        int versionAfterForce = selector.Version;

        // Non-force tick near B -- nodeKeys is empty but _targetLists already cached.
        selector.Tick(150, 0, 0, ZoneA, Array.Empty<string>(), force: false);
        Assert.True(selector.TryGet("quest:test", out var second));
        Assert.Equal("node:b", second.Target.TargetNodeKey);
        // Version must increment because the selected identity changed.
        Assert.True(selector.Version > versionAfterForce);
    }

    [Fact]
    public void Tick_SameTargetNode_DifferentSource_ReroutesToNewSource()
    {
        // Same conceptual character, two physical spawns. The selector must switch
        // when proximity makes a different source better, even though TargetNodeKey
        // stays the same.
        var nearSpawn = MakeTarget(
            ZoneA,
            x: 10f,
            targetNodeKey: "character:bandit",
            sourceKey: "spawn:a"
        );
        var farSpawn = MakeTarget(
            ZoneA,
            x: 100f,
            targetNodeKey: "character:bandit",
            sourceKey: "spawn:b"
        );
        var targets = new[] { nearSpawn, farSpawn };

        var selector = new NavigationTargetSelector(
            (key, _) =>
                key == "quest:test"
                    ? (IReadOnlyList<ResolvedQuestTarget>)targets
                    : Array.Empty<ResolvedQuestTarget>(),
            EmptyRouter()
        );

        selector.Tick(0, 0, 0, ZoneA, new[] { "quest:test" }, force: true);
        Assert.True(selector.TryGet("quest:test", out var first));
        Assert.Equal("spawn:a", first.Target.SourceKey);

        int versionAfterForce = selector.Version;

        selector.Tick(150, 0, 0, ZoneA, Array.Empty<string>(), force: false);
        Assert.True(selector.TryGet("quest:test", out var second));
        Assert.Equal("spawn:b", second.Target.SourceKey);
        Assert.Equal("character:bandit", second.Target.TargetNodeKey);
        Assert.True(selector.Version > versionAfterForce);
    }

    [Fact]
    public void Tick_NoForce_NoChange_DoesNotIncrementVersion()
    {
        // When the player stays near A and nothing moves, Version must not tick up
        // on every frame (avoids unnecessary NavigationEngine selectorChanged triggers).
        var nodeA = MakeTarget(ZoneA, x: 10f, targetNodeKey: "node:a");
        var nodeB = MakeTarget(ZoneA, x: 100f, targetNodeKey: "node:b");
        var targets = new[] { nodeA, nodeB };

        var selector = new NavigationTargetSelector(
            (key, _) =>
                key == "quest:test"
                    ? (IReadOnlyList<ResolvedQuestTarget>)targets
                    : Array.Empty<ResolvedQuestTarget>(),
            EmptyRouter()
        );

        selector.Tick(0, 0, 0, ZoneA, new[] { "quest:test" }, force: true);
        int v1 = selector.Version;

        // Multiple non-force ticks at the same position -- same winner, no version bump.
        selector.Tick(0, 0, 0, ZoneA, Array.Empty<string>(), force: false);
        selector.Tick(0, 0, 0, ZoneA, Array.Empty<string>(), force: false);
        Assert.Equal(v1, selector.Version);
    }

    [Fact]
    public void Tick_ForcePartialRefresh_PreservesUntouchedEntries()
    {
        int aCalls = 0;
        int bCalls = 0;
        var selector = new NavigationTargetSelector(
            (key, _) =>
            {
                if (key == "quest:a")
                {
                    aCalls++;
                    return new[] { MakeTarget(ZoneA, x: 10f, targetNodeKey: "a") };
                }

                if (key == "quest:b")
                {
                    bCalls++;
                    return new[] { MakeTarget(ZoneA, x: 20f, targetNodeKey: "b") };
                }

                return Array.Empty<ResolvedQuestTarget>();
            },
            EmptyRouter()
        );

        selector.Tick(0f, 0f, 0f, ZoneA, new[] { "quest:a", "quest:b", "quest:a" }, force: true);
        Assert.True(selector.TryGet("quest:a", out _));
        Assert.True(selector.TryGet("quest:b", out _));
        Assert.Equal(1, aCalls);
        Assert.Equal(1, bCalls);

        selector.Tick(
            0f,
            0f,
            0f,
            ZoneA,
            new[] { "quest:a", "quest:a" },
            force: true,
            preserveUntouchedEntries: true
        );

        Assert.True(selector.TryGet("quest:a", out _));
        Assert.True(selector.TryGet("quest:b", out _));
        Assert.Equal(2, aCalls);
        Assert.Equal(1, bCalls);
    }

    [Fact]
    public void Tick_NoForce_RefreshesCachedMiningActionabilityFromLiveStateCache()
    {
        var guide = new CompiledGuideBuilder()
            .AddMiningNode("mine:mined", scene: ZoneA, x: 5f, y: 0f, z: 0f)
            .AddMiningNode("mine:available", scene: ZoneA, x: 20f, y: 0f, z: 0f)
            .Build();
        var targets = new[]
        {
            MakeTarget(
                ZoneA,
                x: 5f,
                targetNodeKey: "mine:mined",
                sourceKey: "mine:mined",
                isActionable: true,
                targetNodeType: NodeType.MiningNode
            ),
            MakeTarget(
                ZoneA,
                x: 20f,
                targetNodeKey: "mine:available",
                sourceKey: "mine:available",
                isActionable: true,
                targetNodeType: NodeType.MiningNode
            ),
        };
        var liveState = new FakeSelectorLiveState();
        liveState.MiningAvailability["mine:mined"] = true;
        liveState.MiningAvailability["mine:available"] = true;
        var selector = new NavigationTargetSelector(
            (key, _) =>
                key == "quest:test"
                    ? (IReadOnlyList<ResolvedQuestTarget>)targets
                    : Array.Empty<ResolvedQuestTarget>(),
            EmptyRouter(),
            guide: guide,
            liveState: liveState
        );

        selector.Tick(0f, 0f, 0f, ZoneA, new[] { "quest:test" }, force: true);
        Assert.True(selector.TryGet("quest:test", out var first));
        Assert.Equal("mine:mined", first.Target.TargetNodeKey);

        int versionAfterForce = selector.Version;
        liveState.MiningAvailability["mine:mined"] = false;

        selector.Tick(0f, 0f, 0f, ZoneA, Array.Empty<string>(), force: false);

        Assert.True(selector.TryGet("quest:test", out var second));
        Assert.Equal("mine:available", second.Target.TargetNodeKey);
        Assert.False(targets[0].IsActionable);
        Assert.True(selector.Version > versionAfterForce);
    }

    [Fact]
    public void Tick_NoForce_RefreshesCachedItemBagActionabilityFromLiveStateCache()
    {
        var targets = new[]
        {
            MakeTarget(
                ZoneA,
                x: 5f,
                targetNodeKey: "bag:spent",
                sourceKey: "bag:spent",
                isActionable: true,
                targetNodeType: NodeType.ItemBag
            ),
            MakeTarget(
                ZoneA,
                x: 20f,
                targetNodeKey: "bag:fresh",
                sourceKey: "bag:fresh",
                isActionable: true,
                targetNodeType: NodeType.ItemBag
            ),
        };
        var liveState = new FakeSelectorLiveState();
        liveState.ItemBagAvailability["bag:spent"] = true;
        liveState.ItemBagAvailability["bag:fresh"] = true;
        var selector = new NavigationTargetSelector(
            (key, _) =>
                key == "quest:test"
                    ? (IReadOnlyList<ResolvedQuestTarget>)targets
                    : Array.Empty<ResolvedQuestTarget>(),
            EmptyRouter(),
            liveState: liveState
        );

        selector.Tick(0f, 0f, 0f, ZoneA, new[] { "quest:test" }, force: true);
        Assert.True(selector.TryGet("quest:test", out var first));
        Assert.Equal("bag:spent", first.Target.TargetNodeKey);

        int versionAfterForce = selector.Version;
        liveState.ItemBagAvailability["bag:spent"] = false;

        selector.Tick(0f, 0f, 0f, ZoneA, Array.Empty<string>(), force: false);

        Assert.True(selector.TryGet("quest:test", out var second));
        Assert.Equal("bag:fresh", second.Target.TargetNodeKey);
        Assert.False(targets[0].IsActionable);
        Assert.True(selector.Version > versionAfterForce);
    }

    // -- Blocked-path priority tests -----------------------------------------------

    [Fact]
    public void SelectBest_DirectBeatsBlockedPathSameZone_RegardlessOfDistance()
    {
        // Blocked-path Mineral Deposit at x=5 (closer) vs. direct Fishing at x=20.
        // Direct target must win regardless of proximity.
        var targets = new[]
        {
            MakeTarget(ZoneA, x: 5f, isBlockedPath: true), // blocked, closer
            MakeTarget(ZoneA, x: 20f), // direct, farther
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.True(result!.Value.IsSameZone);
        Assert.Equal(20f, result.Value.Target.X);
        Assert.False(result.Value.IsBlockedPath);
    }

    [Fact]
    public void SelectBest_DirectCrossZoneBeatsBlockedPathSameZone()
    {
        // Direct cross-zone target beats blocked-path same-zone actionable target.
        // Tier 3 (direct cross-zone) must beat tier 4 (blocked same-zone actionable).
        var targets = new[]
        {
            MakeTarget(ZoneA, x: 1f, isBlockedPath: true), // blocked, in-zone
            MakeTarget(ZoneB, x: 999f), // direct, cross-zone
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.False(result!.Value.IsSameZone);
        Assert.Equal(ZoneB, result.Value.Target.Scene);
        Assert.False(result.Value.IsBlockedPath);
    }

    [Fact]
    public void SelectBest_AllBlockedPath_InZoneBeatesCrossZone()
    {
        // When all targets are blocked-path, existing zone/actionable ordering applies.
        // Blocked in-zone (tier 4) must beat blocked cross-zone (tier 6).
        var targets = new[]
        {
            MakeTarget(ZoneB, x: 1f, isBlockedPath: true), // blocked, cross-zone
            MakeTarget(ZoneA, x: 99f, isBlockedPath: true), // blocked, in-zone
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.True(result!.Value.IsSameZone);
        Assert.Equal(ZoneA, result.Value.Target.Scene);
        Assert.True(result.Value.IsBlockedPath);
    }

    [Fact]
    public void SelectBest_IsBlockedPath_ReflectsWinningTarget()
    {
        // When the only available target is blocked-path, IsBlockedPath is true.
        var result = NavigationTargetSelector.SelectBest(
            new[] { MakeTarget(ZoneA, isBlockedPath: true) },
            PX,
            PY,
            PZ,
            ZoneA,
            EmptyRouter()
        );

        Assert.NotNull(result);
        Assert.True(result!.Value.IsBlockedPath);

        // When the winning target is direct, IsBlockedPath is false.
        var result2 = NavigationTargetSelector.SelectBest(
            new[] { MakeTarget(ZoneA) },
            PX,
            PY,
            PZ,
            ZoneA,
            EmptyRouter()
        );

        Assert.NotNull(result2);
        Assert.False(result2!.Value.IsBlockedPath);
    }

    // -- Guaranteed-loot priority tests -------------------------------------------

    [Fact]
    public void SelectBest_CorpseBeatsAliveNPCRegardlessOfDistance()
    {
        // Guaranteed-loot target at 500m must beat a normal actionable at 10m (same zone).
        var targets = new[]
        {
            MakeTarget(
                ZoneA,
                x: 10f,
                isActionable: true,
                isGuaranteedLoot: false,
                targetNodeKey: "alive"
            ),
            MakeTarget(
                ZoneA,
                x: 500f,
                isActionable: true,
                isGuaranteedLoot: true,
                targetNodeKey: "corpse"
            ),
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.True(result!.Value.IsSameZone);
        Assert.Equal("corpse", result.Value.Target.TargetNodeKey);
    }

    [Fact]
    public void SelectBest_ChestBeatsAliveNPC()
    {
        // A chest (IsGuaranteedLoot=true) at 500m must beat a normal actionable at 10m.
        var targets = new[]
        {
            MakeTarget(
                ZoneA,
                x: 10f,
                isActionable: true,
                isGuaranteedLoot: false,
                targetNodeKey: "npc"
            ),
            MakeTarget(
                ZoneA,
                x: 500f,
                isActionable: true,
                isGuaranteedLoot: true,
                targetNodeKey: "chest"
            ),
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.Equal("chest", result.Value.Target.TargetNodeKey);
    }

    [Fact]
    public void SelectBest_GuaranteedLootBlockedDoesNotBeatDirectActionable()
    {
        // A blocked guaranteed-loot target (tier 4) must lose to a direct actionable (tier 1).
        var targets = new[]
        {
            MakeTarget(
                ZoneA,
                x: 500f,
                isActionable: true,
                isGuaranteedLoot: true,
                isBlockedPath: true,
                targetNodeKey: "blocked-chest"
            ),
            MakeTarget(
                ZoneA,
                x: 10f,
                isActionable: true,
                isGuaranteedLoot: false,
                isBlockedPath: false,
                targetNodeKey: "direct-npc"
            ),
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.Equal("direct-npc", result.Value.Target.TargetNodeKey);
    }

    [Fact]
    public void SelectBest_MultipleGuaranteedLootPicksClosest()
    {
        // Two guaranteed-loot targets; the closer one (100m) must win over the farther (400m).
        var targets = new[]
        {
            MakeTarget(
                ZoneA,
                x: 400f,
                isActionable: true,
                isGuaranteedLoot: true,
                targetNodeKey: "far-corpse"
            ),
            MakeTarget(
                ZoneA,
                x: 100f,
                isActionable: true,
                isGuaranteedLoot: true,
                targetNodeKey: "near-corpse"
            ),
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.Equal("near-corpse", result.Value.Target.TargetNodeKey);
    }

    [Fact]
    public void Tick_SkipsNonForcedRerankUntilIntervalElapsed()
    {
        float now = 0f;
        var targets = new[]
        {
            MakeTarget(ZoneA, x: 0f, targetNodeKey: "near"),
            MakeTarget(ZoneA, x: 100f, targetNodeKey: "far"),
        };
        var selector = new NavigationTargetSelector(
            (_, _) => targets,
            EmptyRouter(),
            clock: () => now,
            rerankInterval: 1.0f
        );

        selector.Tick(0f, 0f, 0f, ZoneA, new[] { "quest:a" }, force: true);
        Assert.True(selector.TryGet("quest:a", out var selected));
        Assert.Equal("near", selected.Target.TargetNodeKey);

        now = 0.5f;
        selector.Tick(100f, 0f, 0f, ZoneA, Array.Empty<string>(), force: false);
        Assert.True(selector.TryGet("quest:a", out selected));
        Assert.Equal("near", selected.Target.TargetNodeKey);

        now = 1.1f;
        selector.Tick(100f, 0f, 0f, ZoneA, Array.Empty<string>(), force: false);
        Assert.True(selector.TryGet("quest:a", out selected));
        Assert.Equal("far", selected.Target.TargetNodeKey);
    }

    [Fact]
    public void Tick_ForceBypassesInterval()
    {
        float now = 0f;
        var targets = new[]
        {
            MakeTarget(ZoneA, x: 0f, targetNodeKey: "near"),
            MakeTarget(ZoneA, x: 100f, targetNodeKey: "far"),
        };
        var selector = new NavigationTargetSelector(
            (_, _) => targets,
            EmptyRouter(),
            clock: () => now,
            rerankInterval: 1.0f
        );

        selector.Tick(0f, 0f, 0f, ZoneA, new[] { "quest:a" }, force: true);
        Assert.True(selector.TryGet("quest:a", out var selected));
        Assert.Equal("near", selected.Target.TargetNodeKey);

        now = 0.2f;
        selector.Tick(100f, 0f, 0f, ZoneA, new[] { "quest:a" }, force: true);
        Assert.True(selector.TryGet("quest:a", out selected));
        Assert.Equal("far", selected.Target.TargetNodeKey);
    }

    [Fact]
    public void DumpCandidates_IncludesActionabilityAndSelectionForMatchingTarget()
    {
        var targets = new[]
        {
            MakeTarget(
                ZoneA,
                x: 5f,
                targetNodeKey: "mined",
                sourceKey: "mine:mined",
                isActionable: false
            ),
            MakeTarget(
                ZoneA,
                x: 20f,
                targetNodeKey: "available",
                sourceKey: "mine:available",
                isActionable: true
            ),
        };
        var selector = new NavigationTargetSelector((_, _) => targets, EmptyRouter());

        selector.Tick(PX, PY, PZ, ZoneA, new[] { "quest:a" }, force: true);
        string text = selector.DumpCandidates(PX, PY, PZ, ZoneA, "available");

        Assert.Contains("RequestKey: quest:a", text, StringComparison.Ordinal);
        Assert.Contains("Selected: available", text, StringComparison.Ordinal);
        Assert.Contains("key=mined", text, StringComparison.Ordinal);
        Assert.Contains("actionable=False", text, StringComparison.Ordinal);
        Assert.Contains("key=available", text, StringComparison.Ordinal);
        Assert.Contains("actionable=True", text, StringComparison.Ordinal);
    }

    private sealed class FakeSelectorLiveState : INavigationSelectorLiveState
    {
        public Dictionary<string, bool> MiningAvailability { get; } =
            new(StringComparer.Ordinal);
        public Dictionary<string, bool> ItemBagAvailability { get; } =
            new(StringComparer.Ordinal);

        public (float x, float y, float z)? GetLiveNpcPosition(Node spawnNode) => null;

        public bool IsSpawnEmpty(Node spawnNode) => false;

        public bool TryGetCachedMiningAvailability(Node miningNode, out bool available) =>
            MiningAvailability.TryGetValue(miningNode.Key, out available);

        public bool TryGetCachedItemBagAvailability(Node itemBagNode, out bool available) =>
            ItemBagAvailability.TryGetValue(itemBagNode.Key, out available);
    }
}
