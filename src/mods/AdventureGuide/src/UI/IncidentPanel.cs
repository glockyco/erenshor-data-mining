using System.Numerics;
using AdventureGuide.Config;
using AdventureGuide.Diagnostics;
using ImGuiNET;

namespace AdventureGuide.UI;

internal sealed class IncidentPanel
{
    private const float DefaultWidth = 420f;
    private const float DefaultHeight = 260f;

    private readonly GuideConfig _config;
    private readonly DiagnosticsCore _diagnostics;
    private readonly Func<string> _captureNow;
    private string? _statusMessage;

    internal IncidentPanel(GuideConfig config, DiagnosticsCore diagnostics, Func<string> captureNow)
    {
        _config = config;
        _diagnostics = diagnostics;
        _captureNow = captureNow;
    }

    internal void Render()
    {
        if (!_config.IncidentPanel.Value)
            return;

        ImGui.SetNextWindowSize(new Vector2(DefaultWidth, DefaultHeight), ImGuiCond.FirstUseEver);
        if (!ImGui.Begin("Adventure Guide Incident Diagnostics"))
        {
            ImGui.End();
            return;
        }

        ImGui.TextWrapped(_diagnostics.FormatLastIncidentSummary());
        if (ImGui.Button("Capture now"))
            _statusMessage = _captureNow();
        ImGui.SameLine();
        if (ImGui.Button("Clear counters"))
        {
            _diagnostics.ResetAll();
            _statusMessage = "Diagnostics counters reset.";
        }
        ImGui.SameLine();
        if (ImGui.Button("Copy summary"))
        {
            var summary = _diagnostics.FormatRecentSummary();
            ImGui.SetClipboardText(summary);
            _statusMessage = "Diagnostics summary copied.";
        }

        if (!string.IsNullOrEmpty(_statusMessage))
            ImGui.TextWrapped(_statusMessage);

        ImGui.Separator();
        ImGui.TextUnformatted(_diagnostics.FormatRecentSummary());
        ImGui.End();
    }
}
