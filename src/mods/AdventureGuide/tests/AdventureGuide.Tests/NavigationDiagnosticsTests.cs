using AdventureGuide.Diagnostics;
using AdventureGuide.Navigation;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class NavigationDiagnosticsTests
{
    [Fact]
    public void Tick_RecordsForcedRefreshReason_WhenNavSetVersionChanges()
    {
        var core = new DiagnosticsCore(128, 128, 8, IncidentThresholds.Disabled);
        var selector = new NavigationTargetSelector(
            batchResolver: (_, _) => new Dictionary<string, IReadOnlyList<ResolvedQuestTarget>>(
                StringComparer.Ordinal
            ),
            router: SnapshotHarness.FromBuilder(new CompiledGuideBuilder()).Router,
            diagnostics: core,
            clock: () => 1f,
            rerankInterval: 0f
        );

        selector.Tick(
            0f,
            0f,
            0f,
            "Stowaway",
            new[] { "quest:a" },
            force: true,
            forceReason: DiagnosticTrigger.NavSetChanged
        );

        var spans = core.GetRecentSpans();
        Assert.Contains(spans, span => span.Kind == DiagnosticSpanKind.NavSelectorCollectKeys);
        Assert.Contains(spans, span => span.Kind == DiagnosticSpanKind.NavSelectorBatchResolve);
        var tickSpan = Assert.Single(spans, span => span.Kind == DiagnosticSpanKind.NavSelectorTick);
        Assert.Equal(DiagnosticTrigger.NavSetChanged, tickSpan.Context.Trigger);
    }

    [Fact]
    public void Resolve_RecordsTargetCount_ForResolutionExplosionAccounting()
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
        var unlocks = new UnlockPredicateEvaluator(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            unlocks,
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var core = new DiagnosticsCore(128, 128, 8, IncidentThresholds.Disabled);
        var resolver = new NavigationTargetResolver(
            guide,
            new QuestResolutionService(guide, frontier, sourceResolver, null, versionProvider: () => 0),
            null,
            TestPositionResolvers.Create(guide),
            core
        );

        var results = resolver.Resolve("quest:a", "Forest");

        var snapshot = resolver.ExportDiagnosticsSnapshot();
        Assert.NotEmpty(results);
        Assert.True(snapshot.LastResolvedTargetCount >= results.Count);
    }
}
