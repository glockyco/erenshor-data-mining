using AdventureGuide.Diagnostics;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class IncidentBundleTests
{
    [Fact]
    public void CreateBundle_CopiesEventsSpansAndSnapshots()
    {
        var bundle = IncidentBundle.Create(
            DiagnosticIncident.CreateForTests(DiagnosticIncidentKind.FrameStall, timestampTicks: 1000),
            new[]
            {
                new DiagnosticEvent(
                    DiagnosticEventKind.SceneChanged,
                    DiagnosticsContext.Root(DiagnosticTrigger.SceneChanged),
                    timestampTicks: 900,
                    primaryKey: "scene:stowaway",
                    value0: 0,
                    value1: 0),
            },
            new[]
            {
                new DiagnosticSpan(
                    DiagnosticSpanKind.MarkerRecompute,
                    DiagnosticsContext.Root(DiagnosticTrigger.SceneChanged),
                    startTicks: 910,
                    endTicks: 930,
                    primaryKey: "MarkerComputer",
                    value0: 0,
                    value1: 0),
            },
            new[]
            {
                SnapshotEnvelope.Create(
                    "marker",
                    new MarkerDiagnosticsSnapshot(
                        fullRebuild: true,
                        pendingQuestCount: 3,
                        lastReason: DiagnosticTrigger.SceneChanged,
                        lastDurationTicks: 20,
                        topQuestCosts: Array.Empty<QuestCostSample>(),
                        recentModes: Array.Empty<MarkerRebuildModeSample>())),
            });

        Assert.Equal(DiagnosticIncidentKind.FrameStall, bundle.Incident.Kind);
        Assert.Single(bundle.Events);
        Assert.Single(bundle.Spans);
        Assert.Single(bundle.Snapshots);
    }
}
