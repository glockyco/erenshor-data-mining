using System.Numerics;
using AdventureGuide.Data;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Renders the Progress tab: overall completion, per-zone breakdown, and repeatable quests.
/// Caches all computed data and rebuilds only when QuestStateTracker.IsDirty is true.
/// </summary>
public sealed class ProgressPanel
{
    private readonly GuideData _data;
    private readonly QuestStateTracker _state;

    // Cached progress data, rebuilt when state is dirty
    private int _overallCompleted;
    private int _overallTotal;
    private List<(string zone, int completed, int total)> _zoneSorted = new();
    private bool _hasCachedData;

    public ProgressPanel(GuideData data, QuestStateTracker state)
    {
        _data = data;
        _state = state;
    }

    public void Draw()
    {
        RebuildIfDirty();

        DrawOverallCompletion();
        ImGui.Spacing();
        ImGui.Separator();
        ImGui.Spacing();
        DrawZoneCompletion();
        ImGui.Spacing();
        ImGui.Separator();
        ImGui.Spacing();
        DrawRepeatableQuests();
    }

    private void RebuildIfDirty()
    {
        if (_hasCachedData && !_state.IsDirty)
            return;

        _hasCachedData = true;
        _overallCompleted = 0;
        _overallTotal = 0;

        var zones = new Dictionary<string, (int completed, int total)>(StringComparer.OrdinalIgnoreCase);

        foreach (var quest in _data.All)
        {
            if (IsRepeatable(quest))
                continue;

            _overallTotal++;
            bool done = _state.IsCompleted(quest.DBName);
            if (done) _overallCompleted++;

            string zone = quest.ZoneContext ?? "Unknown";
            if (!zones.TryGetValue(zone, out var counts))
                counts = (0, 0);
            counts.total++;
            if (done) counts.completed++;
            zones[zone] = counts;
        }

        _zoneSorted.Clear();
        foreach (var kvp in zones)
            _zoneSorted.Add((kvp.Key, kvp.Value.completed, kvp.Value.total));

        _zoneSorted.Sort((a, b) =>
        {
            float pctA = a.total > 0 ? (float)a.completed / a.total : 0f;
            float pctB = b.total > 0 ? (float)b.completed / b.total : 0f;
            int cmp = pctB.CompareTo(pctA);
            if (cmp != 0) return cmp;
            return string.Compare(a.zone, b.zone, StringComparison.OrdinalIgnoreCase);
        });
    }

    private void DrawOverallCompletion()
    {
        float fraction = _overallTotal > 0 ? (float)_overallCompleted / _overallTotal : 0f;
        int pct = _overallTotal > 0 ? (int)(fraction * 100f) : 0;

        ImGui.Text("Overall Completion");
        ImGui.ProgressBar(fraction, new Vector2(-1f, 0f), $"{_overallCompleted}/{_overallTotal} quests ({pct}%)");
    }

    private void DrawZoneCompletion()
    {
        ImGui.Text("Zone Completion");
        ImGui.Spacing();

        foreach (var (zone, completed, total) in _zoneSorted)
        {
            float fraction = total > 0 ? (float)completed / total : 0f;
            int pct = total > 0 ? (int)(fraction * 100f) : 0;

            ImGui.Text(zone);
            ImGui.SameLine(0f, 8f);
            ImGui.Text($"({completed}/{total})");
            ImGui.ProgressBar(fraction, new Vector2(-1f, 0f), $"{pct}%");
        }
    }

    private void DrawRepeatableQuests()
    {
        ImGui.Text("Repeatable Quests");
        ImGui.Spacing();

        bool any = false;
        foreach (var quest in _data.All)
        {
            if (!IsRepeatable(quest))
                continue;

            any = true;

            uint color;
            string suffix;
            if (_state.IsCompleted(quest.DBName))
            {
                color = Theme.Success;
                suffix = " [Completed]";
            }
            else if (_state.IsActive(quest.DBName))
            {
                color = Theme.Warning;
                suffix = " [In Progress]";
            }
            else
            {
                color = Theme.TextSecondary;
                suffix = "";
            }

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            ImGui.Text(quest.DisplayName + suffix);
            ImGui.PopStyleColor();
        }

        if (!any)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.Text("No repeatable quests in the guide.");
            ImGui.PopStyleColor();
        }
    }

    private static bool IsRepeatable(QuestEntry quest) =>
        quest.Flags is { Repeatable: true };
}
