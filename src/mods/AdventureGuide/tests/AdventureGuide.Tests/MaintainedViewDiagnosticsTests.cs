using AdventureGuide.Diagnostics;
using AdventureGuide.Navigation;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using AdventureGuide.UI.Tree;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class MaintainedViewDiagnosticsTests
{
    [Fact]
    public void SelectorSnapshot_ExposesBatchScopeAndTopQuestCosts()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver", scene: "Forest", x: 10f, y: 20f, z: 30f)
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
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var positionRegistry = TestPositionResolvers.Create(guide);
        var resolver = new NavigationTargetResolver(
            guide,
            ResolutionTestFactory.BuildService(
                guide,
                frontier,
                sourceResolver,
                zoneRouter: null,
                positionRegistry: positionRegistry
            ),
            null,
            positionRegistry,
            ResolutionTestFactory.BuildProjector(guide, positionRegistry, null)
        );
        var selector = new NavigationTargetSelector(
            (keys, scene) => resolver.ResolveBatch(keys, scene),
            SnapshotHarness.FromBuilder(new CompiledGuideBuilder()).Router,
            guide,
            liveState: null,
            diagnostics: new DiagnosticsCore(128, 128, 8, IncidentThresholds.Disabled),
            clock: () => 1f,
            rerankInterval: 0f
        );

        selector.Tick(
            0f,
            0f,
            0f,
            "Forest",
            new[] { "quest:a" },
            force: true,
            forceReason: DiagnosticTrigger.TargetSourceVersionChanged
        );

        var snapshot = selector.ExportDiagnosticsSnapshot();
        var snapshotType = snapshot.GetType();

        Assert.NotNull(snapshotType.GetProperty("LastBatchKeyCount"));
        Assert.NotNull(snapshotType.GetProperty("LastBatchWasPartialRefresh"));
        Assert.NotNull(snapshotType.GetProperty("TopQuestCosts"));
    }

    [Fact]
    public void SpecTreeSnapshot_ExposesInvalidationScope()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:lucian")
            .AddUnlockPredicate("char:lucian", "quest:root")
            .AddQuest("quest:root", dbName: "ROOT", completers: new[] { "char:lucian" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory.BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty, diagnostics: new DiagnosticsCore(64, 64, 8, IncidentThresholds.Disabled)).Projector;

        projector.GetRootChildren(FindQuestIndex(guide, "quest:root"));

        var snapshot = projector.ExportDiagnosticsSnapshot();
        var snapshotType = snapshot.GetType();

        Assert.NotNull(snapshotType.GetProperty("LastInvalidatedQuestCount"));
        Assert.NotNull(snapshotType.GetProperty("LastInvalidationWasFull"));
    }

    [Fact]
    public void SpecTreeSnapshot_DoesNotInvalidateResolutionServiceOnTrackerVersionChangeAlone()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:lucian")
            .AddUnlockPredicate("char:lucian", "quest:root")
            .AddQuest("quest:root", dbName: "ROOT", completers: new[] { "char:lucian" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var (service, projector) = ResolutionTestFactory.BuildSpecTreeProjector(
            guide,
            tracker,
            currentSceneProvider: () => string.Empty,
            diagnostics: new DiagnosticsCore(64, 64, 8, IncidentThresholds.Disabled)
        );

        int questIndex = FindQuestIndex(guide, "quest:root");
        var before = projector.GetRecord(questIndex);
        // An empty invalidation touches nothing: no fact revision changes, no entry
        // is marked stale, and the engine returns the same cached record. The
        // planner-diagnostics counters under test must stay at zero.
        service.Engine.InvalidateFacts(Array.Empty<FactKey>());
        var after = projector.GetRecord(questIndex);
        var snapshot = projector.ExportDiagnosticsSnapshot();

        Assert.Same(before, after);
        Assert.Equal(0, snapshot.LastInvalidatedQuestCount);
        Assert.False(snapshot.LastInvalidationWasFull);
        Assert.Equal(after, service.ReadQuestResolution("quest:root", string.Empty));
    }

    private static int FindQuestIndex(AdventureGuide.CompiledGuide.CompiledGuide guide, string key)
    {
        Assert.True(guide.TryGetNodeId(key, out int nodeId));
        for (int questIndex = 0; questIndex < guide.QuestCount; questIndex++)
        {
            if (guide.QuestNodeId(questIndex) == nodeId)
                return questIndex;
        }

        throw new InvalidOperationException($"Quest '{key}' not found in compiled guide.");
    }
}
