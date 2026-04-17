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
}
