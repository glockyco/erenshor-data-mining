using AdventureGuide.Diagnostics;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class DiagnosticsCoreTests
{
    [Fact]
    public void RecordEvent_KeepsOnlyConfiguredRecentWindow()
    {
        var core = new DiagnosticsCore(
            eventCapacity: 4,
            spanCapacity: 4,
            incidentCapacity: 8,
            incidentThresholds: IncidentThresholds.Disabled
        );

        for (int i = 0; i < 6; i++)
        {
            core.RecordEvent(
                new DiagnosticEvent(
                    DiagnosticEventKind.NavSetChanged,
                    DiagnosticsContext.Root(DiagnosticTrigger.NavSetChanged),
                    timestampTicks: i,
                    primaryKey: $"quest:{i}",
                    value0: i,
                    value1: 0
                )
            );
        }

        var events = core.GetRecentEvents();
        Assert.Collection(
            events,
            e => Assert.Equal("quest:2", e.PrimaryKey),
            e => Assert.Equal("quest:3", e.PrimaryKey),
            e => Assert.Equal("quest:4", e.PrimaryKey),
            e => Assert.Equal("quest:5", e.PrimaryKey)
        );
    }

    [Fact]
    public void EndSpan_PreservesTriggerReasonAndDuration()
    {
        var core = new DiagnosticsCore(
            eventCapacity: 8,
            spanCapacity: 8,
            incidentCapacity: 8,
            incidentThresholds: IncidentThresholds.Disabled
        );
        var context = DiagnosticsContext.Root(
            DiagnosticTrigger.InventoryChanged,
            correlationId: 42
        );

        var token = core.BeginSpan(
            DiagnosticSpanKind.MarkerRecompute,
            context,
            primaryKey: "quest:a"
        );
        core.EndSpan(token, elapsedTicks: 1234, value0: 7, value1: 1);

        var span = Assert.Single(core.GetRecentSpans());
        Assert.Equal(DiagnosticTrigger.InventoryChanged, span.Context.Trigger);
        Assert.Equal(42, span.Context.CorrelationId);
        Assert.Equal(1234, span.ElapsedTicks);
        Assert.Equal(7, span.Value0);
        Assert.Equal(1, span.Value1);
    }

    [Fact]
    public void EndSpan_FrameStallIncidentIncludesSpanKindAndPrimaryKey()
    {
        var thresholds = new IncidentThresholds(
            frameHitchTicks: long.MaxValue,
            frameStallTicks: 1,
            rebuildStormCount: int.MaxValue,
            rebuildStormWindowTicks: long.MaxValue,
            resolutionExplosionTargetCount: int.MaxValue
        );
        var core = new DiagnosticsCore(
            eventCapacity: 8,
            spanCapacity: 8,
            incidentCapacity: 8,
            incidentThresholds: thresholds
        );

        var token = core.BeginSpan(
            DiagnosticSpanKind.NavSelectorTick,
            DiagnosticsContext.Root(DiagnosticTrigger.NavSetChanged),
            primaryKey: "Stowaway"
        );
        core.EndSpan(token, elapsedTicks: 5);

        var incident = core.TryGetLastIncident();
        Assert.NotNull(incident);
        Assert.Equal(DiagnosticIncidentKind.FrameStall, incident!.Kind);

        Assert.Contains("NavSelectorTick", incident.Summary);
        Assert.Contains("Stowaway", incident.Summary);
    }

    [Fact]
    public void RebuildStorm_TriggersIncidentCapture()
    {
        var thresholds = new IncidentThresholds(
            frameHitchTicks: long.MaxValue,
            frameStallTicks: long.MaxValue,
            rebuildStormCount: 3,
            rebuildStormWindowTicks: 100,
            resolutionExplosionTargetCount: int.MaxValue
        );
        var core = new DiagnosticsCore(
            eventCapacity: 64,
            spanCapacity: 64,
            incidentCapacity: 8,
            incidentThresholds: thresholds
        );

        for (int i = 0; i < 3; i++)
        {
            core.RecordEvent(
                new DiagnosticEvent(
                    DiagnosticEventKind.MarkerRebuildRequested,
                    DiagnosticsContext.Root(DiagnosticTrigger.LiveWorldChanged),
                    timestampTicks: i * 10,
                    primaryKey: "MarkerComputer",
                    value0: 1,
                    value1: 0
                )
            );
        }

        var incident = core.TryGetLastIncident();
        Assert.NotNull(incident);
        Assert.Equal(DiagnosticIncidentKind.RebuildStorm, incident!.Kind);
    }

    [Fact]
    public void EndSpan_FrameHitchIncidentRetainsTriggerMetadataAndCorrelationWindow()
    {
        var thresholds = new IncidentThresholds(
            frameHitchTicks: 10,
            frameStallTicks: 100,
            rebuildStormCount: int.MaxValue,
            rebuildStormWindowTicks: long.MaxValue,
            resolutionExplosionTargetCount: int.MaxValue
        );
        var core = new DiagnosticsCore(eventCapacity: 16, spanCapacity: 16, incidentCapacity: 4, thresholds);
        var context = DiagnosticsContext.Root(DiagnosticTrigger.InventoryChanged, correlationId: 42);

        core.RecordEvent(
            new DiagnosticEvent(
                DiagnosticEventKind.InventoryChanged,
                context,
                timestampTicks: 10,
                primaryKey: "quest:lunchbag1",
                value0: 1,
                value1: 0
            )
        );

        var trigger = core.BeginSpan(
            DiagnosticSpanKind.SpecTreeProjectRoot,
            context,
            primaryKey: "quest:lunchbag1"
        );
        core.EndSpan(trigger, elapsedTicks: 25, value0: 12, value1: 3);

        var bundle = core.TryGetLastIncidentBundle();
        Assert.NotNull(bundle);
        Assert.Equal(DiagnosticIncidentKind.FrameHitch, bundle!.Incident.Kind);
        Assert.Equal(DiagnosticSpanKind.SpecTreeProjectRoot, bundle.Incident.TriggerSpanKind);
        Assert.Equal("quest:lunchbag1", bundle.Incident.TriggerPrimaryKey);
        Assert.Equal(25, bundle.Incident.TriggerElapsedTicks);
        Assert.Equal(10, bundle.Incident.ThresholdTicks);
        Assert.Equal(42, bundle.Incident.CorrelationId);
        Assert.Contains(bundle.Spans, span => span.PrimaryKey == "quest:lunchbag1");
        Assert.Contains(bundle.Events, evt => evt.PrimaryKey == "quest:lunchbag1");
    }

    [Fact]
    public void IncidentHistory_KeepsNewestBundlesWithinConfiguredWindow()
    {
        var thresholds = new IncidentThresholds(
            frameHitchTicks: 1,
            frameStallTicks: 50,
            rebuildStormCount: int.MaxValue,
            rebuildStormWindowTicks: long.MaxValue,
            resolutionExplosionTargetCount: int.MaxValue
        );
        var core = new DiagnosticsCore(eventCapacity: 8, spanCapacity: 8, incidentCapacity: 2, thresholds);

        for (int i = 0; i < 3; i++)
        {
            var token = core.BeginSpan(
                DiagnosticSpanKind.NavSelectorTick,
                DiagnosticsContext.Root(DiagnosticTrigger.NavSetChanged, correlationId: i + 1),
                primaryKey: $"quest:{i}"
            );
            core.EndSpan(token, elapsedTicks: 5);
        }

        var incidents = core.GetRecentIncidents();
        Assert.Collection(
            incidents,
            bundle => Assert.Equal("quest:1", bundle.Incident.TriggerPrimaryKey),
            bundle => Assert.Equal("quest:2", bundle.Incident.TriggerPrimaryKey)
        );
    }

    [Fact]
    public void FormatDetailedIncidentAt_ReturnsFormattedIncidentAtIndex()
    {
        var thresholds = new IncidentThresholds(
            frameHitchTicks: 1,
            frameStallTicks: 50,
            rebuildStormCount: int.MaxValue,
            rebuildStormWindowTicks: long.MaxValue,
            resolutionExplosionTargetCount: int.MaxValue
        );
        var core = new DiagnosticsCore(eventCapacity: 8, spanCapacity: 8, incidentCapacity: 3, thresholds);

        // Create two frame hitch incidents
        for (int i = 0; i < 2; i++)
        {
            var token = core.BeginSpan(
                DiagnosticSpanKind.NavSelectorTick,
                DiagnosticsContext.Root(DiagnosticTrigger.NavSetChanged, correlationId: i + 1),
                primaryKey: $"quest:{i}"
            );
            core.EndSpan(token, elapsedTicks: 5);
        }

        // FormatDetailedIncidentAt should return a non-empty formatted string for valid indices
        var formatted = core.FormatDetailedIncidentAt(0);
        Assert.NotEmpty(formatted);
        Assert.NotEqual("No incidents in history.", formatted);
    }

    [Fact]
    public void FormatDetailedIncidentAt_ReturnsMessageWhenNoIncidents()
    {
        var core = new DiagnosticsCore(
            eventCapacity: 8,
            spanCapacity: 8,
            incidentCapacity: 8,
            incidentThresholds: IncidentThresholds.Disabled
        );

        var formatted = core.FormatDetailedIncidentAt(0);
        Assert.Equal("No incidents in history.", formatted);
    }

    [Fact]
    public void FormatIncidentListLabel_ReturnsLabelWithKindAndMilliseconds()
    {
        var thresholds = new IncidentThresholds(
            frameHitchTicks: 1,
            frameStallTicks: 50,
            rebuildStormCount: int.MaxValue,
            rebuildStormWindowTicks: long.MaxValue,
            resolutionExplosionTargetCount: int.MaxValue
        );
        var core = new DiagnosticsCore(eventCapacity: 8, spanCapacity: 8, incidentCapacity: 3, thresholds);

        // Create a frame hitch incident
        var token = core.BeginSpan(
            DiagnosticSpanKind.NavSelectorTick,
            DiagnosticsContext.Root(DiagnosticTrigger.NavSetChanged),
            primaryKey: "quest:test"
        );
        core.EndSpan(token, elapsedTicks: 5);

        // FormatIncidentListLabel should return a formatted label with index, kind, and time
        var label = core.FormatIncidentListLabel(0);
        Assert.StartsWith("[0]", label);
        Assert.Contains("FrameHitch", label);
        Assert.Contains("ms", label);
    }

    [Fact]
    public void FormatIncidentListLabel_ReturnsInvalidForOutOfRangeIndex()
    {
        var core = new DiagnosticsCore(
            eventCapacity: 8,
            spanCapacity: 8,
            incidentCapacity: 8,
            incidentThresholds: IncidentThresholds.Disabled
        );

        var label = core.FormatIncidentListLabel(0);
        Assert.Equal("[0] (invalid)", label);
    }
}
