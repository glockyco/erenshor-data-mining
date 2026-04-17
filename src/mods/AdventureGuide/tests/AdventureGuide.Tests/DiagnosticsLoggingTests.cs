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

public sealed class DiagnosticsLoggingTests
{
    [Fact]
    public void RepeatedMarkerRecomputes_DoNotEmitPerLoopColdRebuildSpam()
    {
        var logs = new List<string>();
        GuideDiagnostics.LogInfo = logs.Add;

        var core = new DiagnosticsCore(64, 64, IncidentThresholds.Disabled);
        var marker = CreateMarkerComputer(core);

        for (int i = 0; i < 5; i++)
        {
            marker.MarkDirty();
            marker.Recompute();
        }

        Assert.DoesNotContain(logs, line => line.Contains("Cold marker rebuild", StringComparison.Ordinal));
        GuideDiagnostics.LogInfo = null;
    }

    private static MarkerComputer CreateMarkerComputer(DiagnosticsCore core)
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:a", dbName: "QUESTA")
            .Build();
        var dependencies = new GuideDependencyEngine();
        var tracker = new QuestStateTracker(guide, dependencies);
        tracker.LoadState(
            currentZone: "Forest",
            activeQuests: Array.Empty<string>(),
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(),
            keyringItemKeys: Array.Empty<string>());

        var navSet = new NavigationSet();
        navSet.Override("quest:a");
        var trackerState = new TrackerState();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var effectiveFrontier = new EffectiveFrontier(guide, phases);
        var compiledUnlocks = new UnlockPredicateEvaluator(guide, phases);
        var sourceResolver = new SourceResolver(guide, phases, compiledUnlocks, new StubLivePositionProvider());
        var markerResolver = new MarkerQuestTargetResolver(guide, effectiveFrontier, sourceResolver);

        return new MarkerComputer(
            guide,
            tracker,
            null!,
            navSet,
            trackerState,
            markerResolver,
            effectiveFrontier,
            sourceResolver,
            core);
    }
}
