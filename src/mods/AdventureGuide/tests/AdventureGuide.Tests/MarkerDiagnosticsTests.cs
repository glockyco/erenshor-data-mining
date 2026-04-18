using AdventureGuide.Diagnostics;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class MarkerDiagnosticsTests
{
    [Fact]
    public void ApplyGuideChangeSet_RecordsFullRebuildReasonForSceneChanges()
    {
        var marker = CreateMarkerComputer(
            new DiagnosticsCore(64, 64, 8, IncidentThresholds.Disabled)
        );

        marker.ApplyGuideChangeSet(
            new GuideChangeSet(
                inventoryChanged: false,
                questLogChanged: false,
                sceneChanged: true,
                liveWorldChanged: false,
                changedItemKeys: Array.Empty<string>(),
                changedQuestDbNames: Array.Empty<string>(),
                affectedQuestKeys: Array.Empty<string>(),
                changedFacts: Array.Empty<GuideFactKey>()
            )
        );

        var snapshot = marker.ExportDiagnosticsSnapshot();
        Assert.True(snapshot.FullRebuild);
        Assert.Equal(DiagnosticTrigger.SceneChanged, snapshot.LastReason);
    }

    [Fact]
    public void Recompute_RecordsTopQuestCostSample()
    {
        var marker = CreateMarkerComputer(
            new DiagnosticsCore(128, 128, 8, IncidentThresholds.Disabled)
        );

        marker.MarkDirty();
        marker.Recompute();

        var snapshot = marker.ExportDiagnosticsSnapshot();
        Assert.NotEmpty(snapshot.TopQuestCosts);
    }

    [Fact]
    public void Recompute_RecordsSegmentedSceneRebuildSpans()
    {
        var core = new DiagnosticsCore(128, 128, 8, IncidentThresholds.Disabled);
        var marker = CreateMarkerComputer(core);

        marker.MarkDirty();
        marker.Recompute();

        var spanKinds = core.GetRecentSpans().Select(span => span.Kind.ToString()).ToArray();
        Assert.Contains("MarkerCollectSceneQuestKeys", spanKinds);
        Assert.Contains("MarkerRebuildSceneQuestTargets", spanKinds);
        Assert.Contains("MarkerPublishMarkers", spanKinds);
    }

    private static MarkerComputer CreateMarkerComputer(DiagnosticsCore core)
    {
        var guide = new Helpers.CompiledGuideBuilder()
            .AddQuest("quest:a", dbName: "QUESTA")
            .Build();
        var dependencies = new GuideDependencyEngine();
        var tracker = new QuestStateTracker(guide, dependencies);
        tracker.LoadState(
            currentZone: "Forest",
            activeQuests: Array.Empty<string>(),
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(),
            keyringItemKeys: Array.Empty<string>()
        );

        var navSet = new NavigationSet();
        navSet.Override("quest:a");
        var trackerState = new TrackerState();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var effectiveFrontier = new EffectiveFrontier(guide, phases);
        var compiledUnlocks = new UnlockPredicateEvaluator(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            compiledUnlocks,
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var markerResolver = new MarkerQuestTargetResolver(guide, ResolutionTestFactory.BuildService(guide, effectiveFrontier, sourceResolver, zoneRouter: null));

        return new MarkerComputer(
            guide,
            tracker,
            null!,
            navSet,
            trackerState,
            markerResolver,
            effectiveFrontier,
            sourceResolver,
            core
        );
    }
}
