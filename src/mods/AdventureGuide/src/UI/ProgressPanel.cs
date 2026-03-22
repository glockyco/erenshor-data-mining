using System.Numerics;
using AdventureGuide.Data;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Renders the Progress tab: overall completion, per-zone breakdown, and repeatable quests.
/// </summary>
public sealed class ProgressPanel
{
    private readonly GuideData _data;
    private readonly QuestStateTracker _state;

    public ProgressPanel(GuideData data, QuestStateTracker state)
    {
        _data = data;
        _state = state;
    }

    public void Draw()
    {
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

    private void DrawOverallCompletion()
    {
        var (completed, total) = GetOverallCompletion();
        float fraction = total > 0 ? (float)completed / total : 0f;
        int pct = total > 0 ? (int)(fraction * 100f) : 0;

        ImGui.Text("Overall Completion");
        ImGui.ProgressBar(fraction, new Vector2(-1f, 0f), $"{completed}/{total} quests ({pct}%)");
    }

    private void DrawZoneCompletion()
    {
        ImGui.Text("Zone Completion");
        ImGui.Spacing();

        // Group non-repeatable quests by zone, compute completion, sort by % descending.
        var zones = new Dictionary<string, (int completed, int total)>(StringComparer.OrdinalIgnoreCase);

        foreach (var quest in _data.All)
        {
            if (IsRepeatable(quest))
                continue;

            string zone = quest.ZoneContext ?? "Unknown";
            if (!zones.TryGetValue(zone, out var counts))
                counts = (0, 0);

            counts.total++;
            if (_state.IsCompleted(quest.DBName))
                counts.completed++;

            zones[zone] = counts;
        }

        // Sort by completion percentage descending so finished zones float to top.
        var sorted = new List<(string zone, int completed, int total)>(zones.Count);
        foreach (var kvp in zones)
            sorted.Add((kvp.Key, kvp.Value.completed, kvp.Value.total));

        sorted.Sort((a, b) =>
        {
            float pctA = a.total > 0 ? (float)a.completed / a.total : 0f;
            float pctB = b.total > 0 ? (float)b.completed / b.total : 0f;
            int cmp = pctB.CompareTo(pctA);
            if (cmp != 0) return cmp;
            return string.Compare(a.zone, b.zone, StringComparison.OrdinalIgnoreCase);
        });

        foreach (var (zone, completed, total) in sorted)
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

            Vector4 color;
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

            ImGui.TextColored(color, quest.DisplayName + suffix);
        }

        if (!any)
            ImGui.TextColored(Theme.TextSecondary, "No repeatable quests in the guide.");
    }

    /// <summary>
    /// Returns (completed, total) non-repeatable quests for the given zone.
    /// </summary>
    private (int completed, int total) GetZoneCompletion(string zone)
    {
        int completed = 0;
        int total = 0;

        foreach (var quest in _data.All)
        {
            if (IsRepeatable(quest))
                continue;

            if (!string.Equals(quest.ZoneContext, zone, StringComparison.OrdinalIgnoreCase))
                continue;

            total++;
            if (_state.IsCompleted(quest.DBName))
                completed++;
        }

        return (completed, total);
    }

    /// <summary>
    /// Returns (completed, total) for all non-repeatable quests.
    /// </summary>
    private (int completed, int total) GetOverallCompletion()
    {
        int completed = 0;
        int total = 0;

        foreach (var quest in _data.All)
        {
            if (IsRepeatable(quest))
                continue;

            total++;
            if (_state.IsCompleted(quest.DBName))
                completed++;
        }

        return (completed, total);
    }

    private static bool IsRepeatable(QuestEntry quest) =>
        quest.Flags is { Repeatable: true };
}
