using System.Numerics;
using AdventureGuide.Config;
using AdventureGuide.Diagnostics;
using ImGuiNET;

namespace AdventureGuide.UI;

internal sealed class IncidentPanel
{
    private const float DefaultWidth = 720f;
    private const float DefaultHeight = 420f;
    private const float ListWidth = 280f;

    private readonly GuideConfig _config;
    private readonly DiagnosticsCore _diagnostics;
    private readonly Func<string> _captureNow;
    private string? _statusMessage;
    private int _selectedIncidentIndex = 0;

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

        var incidents = _diagnostics.GetRecentIncidents();
        
        // Clamp selected index when history shrinks
        if (_selectedIncidentIndex >= incidents.Count && incidents.Count > 0)
            _selectedIncidentIndex = incidents.Count - 1;
        else if (incidents.Count == 0)
            _selectedIncidentIndex = 0;

        if (ImGui.Button("Capture now"))
            _statusMessage = _captureNow();
        ImGui.SameLine();
        if (ImGui.Button("Clear counters"))
        {
            _diagnostics.ResetAll();
            _selectedIncidentIndex = 0;
            _statusMessage = "Diagnostics counters reset.";
        }
        ImGui.SameLine();
        if (ImGui.Button("Copy summary"))
        {
            ImGui.SetClipboardText(_diagnostics.FormatCompactIncidentSummary());
            _statusMessage = "Diagnostics summary copied.";
        }
        ImGui.SameLine();
        if (ImGui.Button("Copy incident detail"))
        {
            ImGui.SetClipboardText(_diagnostics.FormatDetailedIncidentAt(_selectedIncidentIndex));
            _statusMessage = "Incident detail copied.";
        }

        if (!string.IsNullOrEmpty(_statusMessage))
            ImGui.TextWrapped(_statusMessage);

        ImGui.BeginChild("incident-list", new Vector2(ListWidth, 0f), true);
        for (int i = incidents.Count - 1; i >= 0; i--)
        {
            bool selected = _selectedIncidentIndex == i;
            string label = _diagnostics.FormatIncidentListLabel(i);
            if (ImGui.Selectable(label, selected))
                _selectedIncidentIndex = i;
        }
        ImGui.EndChild();

        ImGui.SameLine();
        ImGui.BeginChild("incident-detail", Vector2.Zero, true);
        ImGui.TextWrapped(_diagnostics.FormatDetailedIncidentAt(_selectedIncidentIndex));
        ImGui.EndChild();
        ImGui.End();
    }
}
