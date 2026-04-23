using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Navigation.Queries;
using AdventureGuide.Frontier;
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
    internal static ZoneRouter EmptyRouter() =>
        SnapshotHarness.FromBuilder(new CompiledGuideBuilder()).Router;

    private static SelectorTargetSet Navigable(params string[] keys) => new(keys);

    private static NavigationTargetSnapshot Snapshot(
        string questKey,
        string scene,
        IReadOnlyList<ResolvedQuestTarget> targets)
    {
        return new NavigationTargetSnapshot(questKey, scene, targets);
    }

    private static NavigationTargetSnapshots Snapshots(
        string scene,
        params NavigationTargetSnapshot[] snapshots) =>
        new(scene, snapshots);

    internal static NavigationTargetSnapshots SnapshotSet(
        string scene,
        string questKey,
        IReadOnlyList<ResolvedQuestTarget> targets) =>
        Snapshots(scene, Snapshot(questKey, scene, targets));

    private sealed class TrackingTargetList : IReadOnlyList<ResolvedQuestTarget>
    {
        private readonly IReadOnlyList<ResolvedQuestTarget> _inner;

        public TrackingTargetList(IReadOnlyList<ResolvedQuestTarget> inner)
        {
            _inner = inner;
        }

        public int IndexerReadCount { get; private set; }

        public ResolvedQuestTarget this[int index]
        {
            get
            {
                IndexerReadCount++;
                return _inner[index];
            }
        }

        public int Count => _inner.Count;

        public void Reset()
        {
            IndexerReadCount = 0;
        }

        public IEnumerator<ResolvedQuestTarget> GetEnumerator() => _inner.GetEnumerator();

        System.Collections.IEnumerator System.Collections.IEnumerable.GetEnumerator() => GetEnumerator();
    }

    /// <summary>

    /// Builds a minimal <see cref="ResolvedQuestTarget"/> with only the fields that
    /// <see cref="NavigationTargetSelector.SelectBest"/> actually reads:
    /// <c>Scene</c>, <c>X/Y/Z</c>, <c>IsActionable</c>, and <c>Semantic.GoalKind</c>.
    /// All other fields receive stub values.
    /// </summary>
    internal static ResolvedQuestTarget MakeTarget(
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
        NodeType targetNodeType = NodeType.Character,
        string? explanationPrimaryText = null
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
            explanationPrimaryText ?? targetNodeKey,
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

    internal static NavigationTargetSelector MakeSelector(
        ZoneRouter router,
        AdventureGuide.CompiledGuide.CompiledGuide? guide = null,
        INavigationSelectorLiveState? liveState = null,
        DiagnosticsCore? diagnostics = null,
        Func<float>? clock = null,
        float rerankInterval = 0f,
        Func<IReadOnlyList<QuestCostSample>>? topQuestCostProvider = null)
    {
        return new NavigationTargetSelector(
            router,
            guide,
            liveState,
            diagnostics,
            clock,
            rerankInterval,
            topQuestCostProvider
        );
    }


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
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var unlocks = new UnlockPredicateEvaluator(guide, phases);
        var positionRegistry = TestPositionResolvers.Create(guide);
        var harness = SnapshotHarness.FromSnapshot(
            guide,
            new StateSnapshot { CurrentZone = ZoneA }
        );
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            unlocks,
            new StubLivePositionProvider(),
            positionRegistry
        );
        var navigationResolver = new NavigationTargetResolver(
            guide,
            ResolutionTestFactory.BuildService(
                guide,
                frontier,
                sourceResolver,
                zoneRouter: harness.Router,
                positionRegistry: positionRegistry
            ),
            harness.Router,
            positionRegistry,
            ResolutionTestFactory.BuildProjector(guide, harness.Router)
        );
        var selector = MakeSelector(harness.Router);
        var snapshots = SnapshotSet(
            ZoneA,
            "quest:a",
            navigationResolver.Resolve("quest:a", ZoneA)
        );

        selector.Tick(0, 0, 0, ZoneA, snapshots, liveWorldChanged: false);

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
        var nodeA = MakeTarget(ZoneA, x: 10f, targetNodeKey: "node:a");
        var nodeB = MakeTarget(ZoneA, x: 100f, targetNodeKey: "node:b");
        var targets = new[] { nodeA, nodeB };
        
        var snapshots = SnapshotSet(ZoneA, "quest:test", targets);
        var selector = MakeSelector(EmptyRouter());

        selector.Tick(0, 0, 0, ZoneA, snapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:test", out var first));
        Assert.Equal("node:a", first.Target.TargetNodeKey);

        selector.Tick(150, 0, 0, ZoneA, snapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:test", out var second));
        Assert.Equal("node:b", second.Target.TargetNodeKey);
    }

    [Fact]
    public void Tick_SameTargetNode_DifferentSource_ReroutesToNewSource()
    {
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
        
        var snapshots = SnapshotSet(ZoneA, "quest:test", targets);
        var selector = MakeSelector(EmptyRouter());

        selector.Tick(0, 0, 0, ZoneA, snapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:test", out var first));
        Assert.Equal("spawn:a", first.Target.SourceKey);

        selector.Tick(150, 0, 0, ZoneA, snapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:test", out var second));
        Assert.Equal("spawn:b", second.Target.SourceKey);
        Assert.Equal("character:bandit", second.Target.TargetNodeKey);
    }

    [Fact]
    public void Tick_ReferenceEqualNavigableSet_KeepsSameWinnerWhenInputsDoNotChange()
    {
        var nodeA = MakeTarget(ZoneA, x: 10f, targetNodeKey: "node:a");
        var nodeB = MakeTarget(ZoneA, x: 100f, targetNodeKey: "node:b");
        var targets = new[] { nodeA, nodeB };
        
        var snapshots = SnapshotSet(ZoneA, "quest:test", targets);
        var selector = MakeSelector(EmptyRouter());

        selector.Tick(0, 0, 0, ZoneA, snapshots, liveWorldChanged: false);
        selector.Tick(0, 0, 0, ZoneA, snapshots, liveWorldChanged: false);
        selector.Tick(0, 0, 0, ZoneA, snapshots, liveWorldChanged: false);

        Assert.True(selector.TryGet("quest:test", out var selected));
        Assert.Equal("node:a", selected.Target.TargetNodeKey);
    }

    [Fact]
    public void Tick_StableNavigableSet_RefreshesWhenSnapshotReferenceChanges()
    {
        var near = new[] { MakeTarget(ZoneA, x: 10f, targetNodeKey: "near") };
        var far = new[] { MakeTarget(ZoneA, x: 100f, targetNodeKey: "far") };
        
        var selector = MakeSelector(EmptyRouter());
        var firstSnapshots = SnapshotSet(ZoneA, "quest:test", near);
        var secondSnapshots = SnapshotSet(ZoneA, "quest:test", far);

        selector.Tick(PX, PY, PZ, ZoneA, firstSnapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:test", out var first));
        Assert.Equal("near", first.Target.TargetNodeKey);

        selector.Tick(PX, PY, PZ, ZoneA, secondSnapshots, liveWorldChanged: false);

        Assert.True(selector.TryGet("quest:test", out var second));
        Assert.Equal("far", second.Target.TargetNodeKey);
    }

    [Fact]
    public void Tick_SnapshotWrapperDelta_RebuildsOnlyChangedQuestEntry()
    {
        var unchangedTargets = new TrackingTargetList(
            new[] { MakeTarget(ZoneA, x: 10f, targetNodeKey: "unchanged") }
        );
        var firstChangedTargets = new[] { MakeTarget(ZoneA, x: 30f, targetNodeKey: "changed:first") };
        var secondChangedTargets = new[] { MakeTarget(ZoneA, x: 5f, targetNodeKey: "changed:second") };
        
        var selector = MakeSelector(EmptyRouter());
        var firstSnapshots = Snapshots(
            ZoneA,
            Snapshot("quest:unchanged", ZoneA, unchangedTargets),
            Snapshot("quest:changed", ZoneA, firstChangedTargets)
        );
        var secondSnapshots = Snapshots(
            ZoneA,
            Snapshot("quest:unchanged", ZoneA, unchangedTargets),
            Snapshot("quest:changed", ZoneA, secondChangedTargets)
        );

        selector.Tick(PX, PY, PZ, ZoneA, firstSnapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:unchanged", out var unchangedFirst));
        Assert.True(selector.TryGet("quest:changed", out var changedFirst));
        Assert.Equal("unchanged", unchangedFirst.Target.TargetNodeKey);
        Assert.Equal("changed:first", changedFirst.Target.TargetNodeKey);
        Assert.True(unchangedTargets.IndexerReadCount > 0);

        unchangedTargets.Reset();

        selector.Tick(PX, PY, PZ, ZoneA, secondSnapshots, liveWorldChanged: false);

        Assert.True(selector.TryGet("quest:unchanged", out var unchangedSecond));
        Assert.True(selector.TryGet("quest:changed", out var changedSecond));
        Assert.Equal("unchanged", unchangedSecond.Target.TargetNodeKey);
        Assert.Equal("changed:second", changedSecond.Target.TargetNodeKey);
        Assert.Equal(0, unchangedTargets.IndexerReadCount);
    }


    /// <summary>
    /// Pins the engine's reference-identity contract at the selector consumer.
    /// When <see cref="Engine{T}.Read"/> recomputes a value-equal entry it
    /// returns the prior instance; the selector's force-rebuild check uses
    /// <c>ReferenceEquals(snapshots, _lastSnapshots)</c> and must not emit
    /// <see cref="DiagnosticEventKind.SelectorRefreshForced"/> on reads that
    /// produce the same reference. Three ticks with the same snapshot ref
    /// must emit exactly one forced-refresh event (from the first tick, when
    /// _lastSnapshots was null).
    /// </summary>
    [Fact]
    public void Tick_DoesNotEmitForcedRefresh_WhenSnapshotRefIsUnchanged()
    {
        var nodeA = MakeTarget(ZoneA, x: 10f, targetNodeKey: "node:a");
        var targets = new[] { nodeA };
    
        var snapshots = SnapshotSet(ZoneA, "quest:test", targets);
        var core = new DiagnosticsCore(128, 128, 8, IncidentThresholds.Disabled);
        var selector = MakeSelector(EmptyRouter(), diagnostics: core);

        selector.Tick(PX, PY, PZ, ZoneA, snapshots, liveWorldChanged: false);
        selector.Tick(PX, PY, PZ, ZoneA, snapshots, liveWorldChanged: false);
        selector.Tick(PX, PY, PZ, ZoneA, snapshots, liveWorldChanged: false);

        var events = core.GetRecentEvents();
        int forcedCount = 0;
        foreach (var evt in events)
        {
            if (evt.Kind == DiagnosticEventKind.SelectorRefreshForced)
                forcedCount++;
        }
        Assert.Equal(1, forcedCount);
    }

    [Fact]
    public void Tick_InvalidateTargets_RebuildsSameReferenceTargetsForNewCurrentZone()
    {
        var targets = new[] { MakeTarget(ZoneB, x: 10f, targetNodeKey: "zone-b-target") };
        
        var snapshots = SnapshotSet(ZoneB, "quest:test", targets);
        var selector = MakeSelector(EmptyRouter());

        selector.Tick(PX, PY, PZ, ZoneA, snapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:test", out var first));
        Assert.False(first.IsSameZone);
        Assert.Equal(ZoneB, first.Target.Scene);

        selector.InvalidateTargets();
        selector.Tick(PX, PY, PZ, ZoneB, snapshots, liveWorldChanged: false);

        Assert.True(selector.TryGet("quest:test", out var second));
        Assert.True(second.IsSameZone);
        Assert.Equal(ZoneB, second.Target.Scene);
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
        liveState.Snapshots["mine:mined"] = LiveSourceSnapshot.MiningAvailable("mine:mined", "mine:mined");
        liveState.Snapshots["mine:available"] = LiveSourceSnapshot.MiningAvailable("mine:available", "mine:available");
        
        var snapshots = SnapshotSet(ZoneA, "quest:test", targets);
        var selector = MakeSelector(EmptyRouter(), guide: guide, liveState: liveState);

        selector.Tick(0f, 0f, 0f, ZoneA, snapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:test", out var first));
        Assert.Equal("mine:mined", first.Target.TargetNodeKey);

        liveState.Snapshots["mine:mined"] = LiveSourceSnapshot.Mined("mine:mined", "mine:mined", respawnSeconds: 30f);
        selector.Tick(0f, 0f, 0f, ZoneA, snapshots, liveWorldChanged: false);

        Assert.True(selector.TryGet("quest:test", out var second));
        Assert.Equal("mine:available", second.Target.TargetNodeKey);
        Assert.True(targets[0].IsActionable);
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
        liveState.Snapshots["bag:spent"] = LiveSourceSnapshot.ItemAvailable("bag:spent", "bag:spent");
        liveState.Snapshots["bag:fresh"] = LiveSourceSnapshot.ItemAvailable("bag:fresh", "bag:fresh");
        
        var snapshots = SnapshotSet(ZoneA, "quest:test", targets);
        var selector = MakeSelector(EmptyRouter(), liveState: liveState);

        selector.Tick(0f, 0f, 0f, ZoneA, snapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:test", out var first));
        Assert.Equal("bag:spent", first.Target.TargetNodeKey);

        liveState.Snapshots["bag:spent"] = LiveSourceSnapshot.PickedUp("bag:spent", "bag:spent", respawnSeconds: 30f);
        selector.Tick(0f, 0f, 0f, ZoneA, snapshots, liveWorldChanged: false);

        Assert.True(selector.TryGet("quest:test", out var second));
        Assert.Equal("bag:fresh", second.Target.TargetNodeKey);
        Assert.True(targets[0].IsActionable);
    }

	[Fact]
	public void Tick_ZoneReentrySnapshot_RewritesSelectedTargetExplanationToReenterZone()
	{
		var guide = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: ZoneA)
			.AddSpawnPoint("spawn:direct", scene: ZoneA, x: 5f, y: 0f, z: 0f)
			.Build();
		var targets = new[]
		{
			MakeTarget(
				ZoneA,
				x: 5f,
				targetNodeKey: "char:direct",
				sourceKey: "spawn:direct",
				isActionable: true,
				explanationPrimaryText: "Kill char:direct"),
		};
		var liveState = new FakeSelectorLiveState();
		liveState.Snapshots["char:direct"] = LiveSourceSnapshot.ZoneReentry(
			"spawn:direct",
			"char:direct",
			respawnSeconds: 0f);
		var selector = MakeSelector(EmptyRouter(), guide: guide, liveState: liveState);
		
		var snapshots = SnapshotSet(ZoneA, "quest:test", targets);

		selector.Tick(0f, 0f, 0f, ZoneA, snapshots, liveWorldChanged: false);

		Assert.True(selector.TryGet("quest:test", out var selected));
		Assert.Equal("Re-enter zone", selected.Target.Explanation.PrimaryText);
		Assert.Equal("char:direct", selected.Target.Explanation.SecondaryText);
	}

	[Fact]
	public void Tick_DeadSnapshotWithoutZoneReentry_KeepsOriginalSelectedTargetExplanation()
	{
		var guide = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: ZoneA)
			.AddSpawnPoint("spawn:static", scene: ZoneA, x: 5f, y: 0f, z: 0f)
			.Build();
		var targets = new[]
		{
			MakeTarget(
				ZoneA,
				x: 5f,
				targetNodeKey: "char:static",
				sourceKey: "spawn:static",
				isActionable: true,
				explanationPrimaryText: "Kill char:static"),
		};
		var liveState = new FakeSelectorLiveState();
		liveState.Snapshots["char:static"] = LiveSourceSnapshot.Dead(
			"spawn:static",
			"char:static",
			livePosition: null,
			anchoredLivePosition: null,
			respawnSeconds: 30f);
		var selector = MakeSelector(EmptyRouter(), guide: guide, liveState: liveState);
		
		var snapshots = SnapshotSet(ZoneA, "quest:test", targets);

		selector.Tick(0f, 0f, 0f, ZoneA, snapshots, liveWorldChanged: false);

		Assert.True(selector.TryGet("quest:test", out var selected));
		Assert.Equal("Kill char:static", selected.Target.Explanation.PrimaryText);
		Assert.Null(selected.Target.Explanation.SecondaryText);
	}

	[Fact]
	public void Tick_DeadSnapshotWithCorpseGuaranteedLoot_RemainsSelectedOverCloserAliveTarget()
	{
		var guide = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: ZoneA)
			.AddSpawnPoint("spawn:corpse", scene: ZoneA, x: 50f, y: 0f, z: 0f)
			.Build();
		var targets = new[]
		{
			MakeTarget(
				ZoneA,
				x: 10f,
				targetNodeKey: "char:alive",
				sourceKey: "spawn:alive",
				isActionable: true),
			MakeTarget(
				ZoneA,
				x: 50f,
				targetNodeKey: "char:corpse",
				sourceKey: "spawn:corpse",
				isActionable: true,
				isGuaranteedLoot: true),
		};
		var liveState = new FakeSelectorLiveState();
		liveState.Snapshots["char:corpse"] = LiveSourceSnapshot.Dead(
			"spawn:corpse",
			"char:corpse",
			livePosition: (50f, 0f, 0f),
			anchoredLivePosition: (50f, 0f, 0f),
			respawnSeconds: 30f);
		var selector = MakeSelector(EmptyRouter(), guide: guide, liveState: liveState);
		
		var snapshots = SnapshotSet(ZoneA, "quest:test", targets);

		selector.Tick(0f, 0f, 0f, ZoneA, snapshots, liveWorldChanged: false);

		Assert.True(selector.TryGet("quest:test", out var selected));
		Assert.Equal("char:corpse", selected.Target.TargetNodeKey);
		Assert.True(selected.Target.IsActionable);
		Assert.True(selected.Target.IsGuaranteedLoot);
		Assert.True(selected.IsSameZone);
	}

	[Fact]
	public void Tick_ZoneReentrySnapshot_DemotesDirectlyPlacedDeadSourceBehindCrossZoneObjective()
	{
		var guide = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: ZoneA)
			.AddZone("zone:b", scene: ZoneB)
			.AddZoneLine("zl:ab", scene: ZoneA, destinationZoneKey: "zone:b", x: 10f, y: 0f, z: 0f)
			.AddSpawnPoint("spawn:direct", scene: ZoneA, x: 5f, y: 0f, z: 0f)
			.Build();
		var harness = SnapshotHarness.FromSnapshot(guide, new StateSnapshot { CurrentZone = ZoneA });
		var targets = new[]
		{
			MakeTarget(
				ZoneA,
				x: 5f,
				targetNodeKey: "char:direct",
				sourceKey: "spawn:direct",
				isActionable: true),
			MakeTarget(
				ZoneB,
				x: 50f,
				targetNodeKey: "char:zone-b",
				sourceKey: "spawn:zone-b",
				isActionable: true),
		};
		var liveState = new FakeSelectorLiveState();
		liveState.Snapshots["char:direct"] = LiveSourceSnapshot.ZoneReentry(
			"spawn:direct",
			"char:direct",
			respawnSeconds: 0f);
		var selector = MakeSelector(harness.Router, guide: guide, liveState: liveState);
		
		var snapshots = SnapshotSet(ZoneA, "quest:test", targets);

		selector.Tick(0f, 0f, 0f, ZoneA, snapshots, liveWorldChanged: false);

		Assert.True(selector.TryGet("quest:test", out var selected));
		Assert.Equal("char:zone-b", selected.Target.TargetNodeKey);
		Assert.False(selected.IsSameZone);
		Assert.Equal(1, selected.HopCount);
		Assert.True(targets[0].IsActionable);
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
    public void ResolvedQuestTarget_exposes_availability_priority_for_selector_ranking()
    {
        var property = typeof(ResolvedQuestTarget).GetProperty("AvailabilityPriority");

        Assert.NotNull(property);
        Assert.Contains("Immediate", System.Enum.GetNames(property!.PropertyType));
        Assert.Contains("PrerequisiteFallback", System.Enum.GetNames(property.PropertyType));
    }

    [Fact]
    public void SelectBest_DirectSameZoneActionableBeatsCloserPrerequisiteDerivedTarget()
    {
        var targets = new[]
        {
            MakeTarget(
                ZoneA,
                x: 10f,
                goalKind: NavigationGoalKind.CollectItem,
                targetNodeKey: "prereq-source",
                requiredForQuestKey: "quest:wyland's note"
            ),
            MakeTarget(
                ZoneA,
                x: 100f,
                goalKind: NavigationGoalKind.CollectItem,
                targetNodeKey: "direct-source"
            ),
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.Equal("direct-source", result!.Value.Target.TargetNodeKey);
    }

    [Fact]
    public void SelectBest_SkipsSameZoneTargetsWithoutFiniteWorldPosition()
    {
        var targets = new[]
        {
            MakeTarget(
                ZoneA,
                x: float.NaN,
                y: float.NaN,
                z: float.NaN,
                goalKind: NavigationGoalKind.CollectItem,
                targetNodeKey: "invalid-direct"
            ),
            MakeTarget(
                ZoneA,
                x: 100f,
                goalKind: NavigationGoalKind.CollectItem,
                targetNodeKey: "valid-direct"
            ),
            MakeTarget(
                ZoneA,
                x: 10f,
                goalKind: NavigationGoalKind.CollectItem,
                targetNodeKey: "prereq-near",
                requiredForQuestKey: "quest:wyland's note"
            ),
        };

        var result = NavigationTargetSelector.SelectBest(targets, PX, PY, PZ, ZoneA, EmptyRouter());

        Assert.NotNull(result);
        Assert.Equal("valid-direct", result!.Value.Target.TargetNodeKey);
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
        
        var snapshots = SnapshotSet(ZoneA, "quest:a", targets);
        var selector = MakeSelector(EmptyRouter(), clock: () => now, rerankInterval: 1.0f);

        selector.Tick(0f, 0f, 0f, ZoneA, snapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:a", out var selected));
        Assert.Equal("near", selected.Target.TargetNodeKey);

        now = 0.5f;
        selector.Tick(100f, 0f, 0f, ZoneA, snapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:a", out selected));
        Assert.Equal("near", selected.Target.TargetNodeKey);

        now = 1.1f;
        selector.Tick(100f, 0f, 0f, ZoneA, snapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:a", out selected));
        Assert.Equal("far", selected.Target.TargetNodeKey);
    }

    [Fact]
    public void Tick_SnapshotReferenceChange_BypassesInterval()
    {
        float now = 0f;
        var targets = new[]
        {
            MakeTarget(ZoneA, x: 0f, targetNodeKey: "near"),
            MakeTarget(ZoneA, x: 100f, targetNodeKey: "far"),
        };
        var firstSnapshots = SnapshotSet(ZoneA, "quest:a", targets);
        var secondSnapshots = SnapshotSet(ZoneA, "quest:a", targets);
        var selector = MakeSelector(EmptyRouter(), clock: () => now, rerankInterval: 1.0f);

        selector.Tick(0f, 0f, 0f, ZoneA, firstSnapshots, liveWorldChanged: false);
        Assert.True(selector.TryGet("quest:a", out var selected));
        Assert.Equal("near", selected.Target.TargetNodeKey);

        now = 0.2f;
        selector.Tick(100f, 0f, 0f, ZoneA, secondSnapshots, liveWorldChanged: false);
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
        var selector = MakeSelector(EmptyRouter());
        var snapshots = SnapshotSet(ZoneA, "quest:a", targets);

        selector.Tick(PX, PY, PZ, ZoneA, snapshots, liveWorldChanged: false);
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
        public Dictionary<string, LiveSourceSnapshot> Snapshots { get; } =
            new(StringComparer.Ordinal);

        public LiveSourceSnapshot GetLiveSourceSnapshot(string? sourceNodeKey, Node targetNode) =>
            Snapshots.TryGetValue(targetNode.Key, out var snapshot)
                ? snapshot
                : LiveSourceSnapshot.Unknown(sourceNodeKey, targetNode.Key);

        public bool TryConsumeLiveWorldChange() => false;
    }


    [Fact]
    public void Tick_ExposesSnapshotDrivenContract()
    {
        var tick = typeof(NavigationTargetSelector).GetMethod(
            "Tick",
            System.Reflection.BindingFlags.Instance
                | System.Reflection.BindingFlags.Public
                | System.Reflection.BindingFlags.NonPublic
        );

        Assert.NotNull(tick);
        Assert.Contains(
            tick!.GetParameters(),
            parameter => parameter.ParameterType == typeof(NavigationTargetSnapshots)
        );
    }

    [Fact]
    public void NavigationTargetResolver_ExposesBatchResolveApi()
    {
        Assert.NotNull(
            typeof(NavigationTargetResolver).GetMethod(
                "ResolveBatch",
                System.Reflection.BindingFlags.Instance
                    | System.Reflection.BindingFlags.Public
                    | System.Reflection.BindingFlags.NonPublic
            )
        );
    }
}
