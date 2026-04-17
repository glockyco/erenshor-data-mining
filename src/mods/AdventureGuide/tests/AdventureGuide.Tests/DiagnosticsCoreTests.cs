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
            frameStallTicks: 1,
            rebuildStormCount: int.MaxValue,
            rebuildStormWindowTicks: long.MaxValue,
            resolutionExplosionTargetCount: int.MaxValue
        );
        var core = new DiagnosticsCore(
            eventCapacity: 8,
            spanCapacity: 8,
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
            frameStallTicks: long.MaxValue,
            rebuildStormCount: 3,
            rebuildStormWindowTicks: 100,
            resolutionExplosionTargetCount: int.MaxValue
        );
        var core = new DiagnosticsCore(
            eventCapacity: 64,
            spanCapacity: 64,
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
}
