using AdventureGuide.Diagnostics;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class DebugAPIDiagnosticsTests
{
    [Fact]
    public void DumpPerfSummary_ReturnsIncidentAwareSummary()
    {
        var thresholds = new IncidentThresholds(
            frameHitchTicks: 1,
            frameStallTicks: 10,
            rebuildStormCount: int.MaxValue,
            rebuildStormWindowTicks: long.MaxValue,
            resolutionExplosionTargetCount: int.MaxValue
        );
        var core = new DiagnosticsCore(16, 16, 8, thresholds);
        var token = core.BeginSpan(
            DiagnosticSpanKind.MarkerRecompute,
            DiagnosticsContext.Root(DiagnosticTrigger.SceneChanged),
            primaryKey: "MarkerComputer"
        );
        core.EndSpan(token, elapsedTicks: 20, value0: 1, value1: 0);
        DebugAPI.Diagnostics = core;

        string text = DebugAPI.DumpPerfSummary();

        Assert.Contains("last incident", text, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("MarkerRecompute", text, StringComparison.Ordinal);
        DebugAPI.Diagnostics = null;
    }

    [Fact]
    public void DumpLastIncident_ReturnsNoIncident_WhenNothingCaptured()
    {
        DebugAPI.Diagnostics = new DiagnosticsCore(16, 16, 8, IncidentThresholds.Disabled);

        Assert.Contains(
            "No incident",
            DebugAPI.DumpLastIncident(),
            StringComparison.OrdinalIgnoreCase
        );
        DebugAPI.Diagnostics = null;
    }

    [Fact]
    public void DumpLastIncidentDetailed_UsesDetailedIncidentFormatter()
    {
        var thresholds = new IncidentThresholds(
            frameHitchTicks: 10,
            frameStallTicks: 100,
            rebuildStormCount: int.MaxValue,
            rebuildStormWindowTicks: long.MaxValue,
            resolutionExplosionTargetCount: int.MaxValue
        );
        var core = new DiagnosticsCore(16, 16, 4, thresholds);
        var token = core.BeginSpan(
            DiagnosticSpanKind.SpecTreeProjectRoot,
            DiagnosticsContext.Root(DiagnosticTrigger.InventoryChanged, correlationId: 8),
            primaryKey: "quest:lunchbag1"
        );
        core.EndSpan(token, elapsedTicks: 25, value0: 11, value1: 3);
        DebugAPI.Diagnostics = core;

        string text = DebugAPI.DumpLastIncidentDetailed();

        Assert.Contains("quest:lunchbag1", text, StringComparison.Ordinal);
        Assert.Contains("projected nodes=11", text, StringComparison.Ordinal);
        DebugAPI.Diagnostics = null;
    }

    [Fact]
    public void DumpAllIncidents_ReturnsDetailedHistoryNewestFirst()
    {
        var thresholds = new IncidentThresholds(
            frameHitchTicks: 1,
            frameStallTicks: 50,
            rebuildStormCount: int.MaxValue,
            rebuildStormWindowTicks: long.MaxValue,
            resolutionExplosionTargetCount: int.MaxValue
        );
        var core = new DiagnosticsCore(16, 16, 8, thresholds);

        var first = core.BeginSpan(
            DiagnosticSpanKind.SpecTreeProjectRoot,
            DiagnosticsContext.Root(DiagnosticTrigger.InventoryChanged),
            primaryKey: "quest:first"
        );
        core.EndSpan(first, elapsedTicks: 10, value0: 4, value1: 2);

        var second = core.BeginSpan(
            DiagnosticSpanKind.NavSelectorTick,
            DiagnosticsContext.Root(DiagnosticTrigger.NavSetChanged),
            primaryKey: "quest:second"
        );
        core.EndSpan(second, elapsedTicks: 10);
        DebugAPI.Diagnostics = core;

        string text = DebugAPI.DumpAllIncidents();

        Assert.Contains("=== Incident 1 ===", text, StringComparison.Ordinal);
        Assert.Contains("quest:second", text, StringComparison.Ordinal);
        Assert.Contains("quest:first", text, StringComparison.Ordinal);
        Assert.True(
            text.IndexOf("quest:second", StringComparison.Ordinal)
                < text.IndexOf("quest:first", StringComparison.Ordinal)
        );
        DebugAPI.Diagnostics = null;
    }
}
