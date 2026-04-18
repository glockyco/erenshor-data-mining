using AdventureGuide.Diagnostics;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class IncidentReportFormatterTests
{
    [Fact]
    public void FormatCompact_ReturnsNoneMessage_WhenBundleIsNull()
    {
        string text = IncidentReportFormatter.FormatCompact(null);
        Assert.Contains("none", text, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void FormatCompact_IncludesKindAndTriggerPrimaryKey()
    {
        var incident = new DiagnosticIncident(
            DiagnosticIncidentKind.FrameHitch,
            timestampTicks: 200,
            summary: "Test",
            triggerSpanKind: DiagnosticSpanKind.NavSelectorTick,
            triggerPrimaryKey: "quest:lunchbag1",
            triggerElapsedTicks: 25,
            thresholdTicks: 10,
            correlationId: 1,
            parentSpanId: 0
        );
        var bundle = IncidentBundle.Create(incident, Array.Empty<DiagnosticEvent>(), Array.Empty<DiagnosticSpan>(), Array.Empty<SnapshotEnvelope>());

        string text = IncidentReportFormatter.FormatCompact(bundle);

        Assert.Contains("FrameHitch", text, StringComparison.Ordinal);
        Assert.Contains("quest:lunchbag1", text, StringComparison.Ordinal);
    }

    [Fact]
    public void FormatDetailed_IncludesTriggerDurationThresholdAndTreeMetrics()
    {
        var incident = new DiagnosticIncident(
            DiagnosticIncidentKind.FrameHitch,
            timestampTicks: 200,
            summary: "Span SpecTreeProjectRoot (quest:lunchbag1) exceeded the frame hitch threshold.",
            triggerSpanKind: DiagnosticSpanKind.SpecTreeProjectRoot,
            triggerPrimaryKey: "quest:lunchbag1",
            triggerElapsedTicks: 50,
            thresholdTicks: 30,
            correlationId: 12,
            parentSpanId: 0
        );
        var bundle = IncidentBundle.Create(
            incident,
            Array.Empty<DiagnosticEvent>(),
            new[]
            {
                new DiagnosticSpan(
                    DiagnosticSpanKind.SpecTreeProjectRoot,
                    DiagnosticsContext.Root(DiagnosticTrigger.InventoryChanged, correlationId: 12),
                    startTicks: 100,
                    endTicks: 150,
                    primaryKey: "quest:lunchbag1",
                    value0: 11,
                    value1: 3
                )
            },
            Array.Empty<SnapshotEnvelope>()
        );

        string text = IncidentReportFormatter.FormatDetailed(bundle);

        Assert.Contains("FrameHitch", text, StringComparison.Ordinal);
        Assert.Contains("quest:lunchbag1", text, StringComparison.Ordinal);
        Assert.Contains("Threshold", text, StringComparison.Ordinal);
        Assert.Contains("projected nodes=11", text, StringComparison.Ordinal);
        Assert.Contains("cycle prunes=3", text, StringComparison.Ordinal);
    }

    [Fact]
    public void FormatDetailed_IncludesMarkerSegmentMetrics()
    {
        var incident = new DiagnosticIncident(
            DiagnosticIncidentKind.FrameHitch,
            timestampTicks: 200,
            summary: "Marker rebuild incident",
            triggerSpanKind: (DiagnosticSpanKind)System.Enum.Parse(typeof(DiagnosticSpanKind), "MarkerRebuildCurrentScene"),
            triggerPrimaryKey: "Forest",
            triggerElapsedTicks: 50,
            thresholdTicks: 30,
            correlationId: 12,
            parentSpanId: 0
        );
        var bundle = IncidentBundle.Create(
            incident,
            Array.Empty<DiagnosticEvent>(),
            new[]
            {
                new DiagnosticSpan(
                    (DiagnosticSpanKind)System.Enum.Parse(typeof(DiagnosticSpanKind), "MarkerCollectSceneQuestKeys"),
                    DiagnosticsContext.Root(DiagnosticTrigger.SceneChanged, correlationId: 12),
                    startTicks: 100,
                    endTicks: 150,
                    primaryKey: "Forest",
                    value0: 3,
                    value1: 0
                ),
                new DiagnosticSpan(
                    (DiagnosticSpanKind)System.Enum.Parse(typeof(DiagnosticSpanKind), "MarkerRebuildSceneQuestTargets"),
                    DiagnosticsContext.Root(DiagnosticTrigger.SceneChanged, correlationId: 12),
                    startTicks: 150,
                    endTicks: 190,
                    primaryKey: "Forest",
                    value0: 2,
                    value1: 0
                ),
                new DiagnosticSpan(
                    (DiagnosticSpanKind)System.Enum.Parse(typeof(DiagnosticSpanKind), "MarkerPublishMarkers"),
                    DiagnosticsContext.Root(DiagnosticTrigger.SceneChanged, correlationId: 12),
                    startTicks: 190,
                    endTicks: 210,
                    primaryKey: "Forest",
                    value0: 5,
                    value1: 1
                )
            },
            Array.Empty<SnapshotEnvelope>()
        );

        string text = IncidentReportFormatter.FormatDetailed(bundle);

        Assert.Contains("quest keys=3", text, StringComparison.Ordinal);
        Assert.Contains("quests rebuilt=2", text, StringComparison.Ordinal);
        Assert.Contains("markers=5", text, StringComparison.Ordinal);
        Assert.Contains("suppressed=1", text, StringComparison.Ordinal);
    }

    [Fact]
    public void FormatDetailed_ReturnsUsefulMessage_WhenIncidentHasNoSpans()
    {
        var incident = new DiagnosticIncident(
            DiagnosticIncidentKind.FrameHitch,
            timestampTicks: 200,
            summary: "Test incident",
            triggerSpanKind: null,
            triggerPrimaryKey: null,
            triggerElapsedTicks: 0,
            thresholdTicks: 0,
            correlationId: 0,
            parentSpanId: 0
        );
        var bundle = IncidentBundle.Create(
            incident,
            Array.Empty<DiagnosticEvent>(),
            Array.Empty<DiagnosticSpan>(),
            Array.Empty<SnapshotEnvelope>()
        );

        string text = IncidentReportFormatter.FormatDetailed(bundle);

        Assert.NotEmpty(text);
        Assert.Contains("FrameHitch", text, StringComparison.Ordinal);
    }

    [Fact]
    public void FormatDetailed_IncludesMaintainedViewBatchMetrics()
    {
        var incident = new DiagnosticIncident(
            DiagnosticIncidentKind.FrameStall,
            timestampTicks: 200,
            summary: "Navigation batch incident",
            triggerSpanKind: (DiagnosticSpanKind)System.Enum.Parse(typeof(DiagnosticSpanKind), "NavSelectorBatchResolve"),
            triggerPrimaryKey: "Stowaway",
            triggerElapsedTicks: 50,
            thresholdTicks: 30,
            correlationId: 12,
            parentSpanId: 0
        );
        var bundle = IncidentBundle.Create(
            incident,
            Array.Empty<DiagnosticEvent>(),
            new[]
            {
                new DiagnosticSpan(
                    (DiagnosticSpanKind)System.Enum.Parse(typeof(DiagnosticSpanKind), "NavSelectorCollectKeys"),
                    DiagnosticsContext.Root(DiagnosticTrigger.TargetSourceVersionChanged, correlationId: 12),
                    startTicks: 100,
                    endTicks: 120,
                    primaryKey: "Stowaway",
                    value0: 12,
                    value1: 0
                ),
                new DiagnosticSpan(
                    (DiagnosticSpanKind)System.Enum.Parse(typeof(DiagnosticSpanKind), "NavSelectorBatchResolve"),
                    DiagnosticsContext.Root(DiagnosticTrigger.TargetSourceVersionChanged, correlationId: 12),
                    startTicks: 120,
                    endTicks: 180,
                    primaryKey: "Stowaway",
                    value0: 12,
                    value1: 47
                )
            },
            Array.Empty<SnapshotEnvelope>()
        );

        string text = IncidentReportFormatter.FormatDetailed(bundle);

        Assert.Contains("quest keys=12", text, StringComparison.Ordinal);
        Assert.Contains("resolved targets=47", text, StringComparison.Ordinal);
    }
}
