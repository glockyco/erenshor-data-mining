using AdventureGuide.Data;
using AdventureGuide.State;
using AdventureGuide.UI;

namespace AdventureGuide.Diagnostics;

/// <summary>
/// Static API for runtime inspection via HotRepl.
/// All methods return human-readable strings for eval output.
/// </summary>
public static class DebugAPI
{
    internal static GuideData? Data { get; set; }
    internal static QuestStateTracker? State { get; set; }
    internal static FilterState? Filter { get; set; }

    /// <summary>Dump current mod state: zone, active/completed counts, filter state.</summary>
    public static string DumpState()
    {
        if (State == null) return "State not initialized";

        return $"Zone: {State.CurrentZone}\n"
             + $"Active quests: {State.ActiveQuests.Count}\n"
             + $"Completed quests: {State.CompletedQuests.Count}\n"
             + $"Selected: {State.SelectedQuestDBName ?? "(none)"}\n"
             + $"Filter: {Filter?.FilterMode ?? QuestFilterMode.Active}\n"
             + $"Search: '{Filter?.SearchText ?? ""}'\n"
             + $"Zone filter: {Filter?.ZoneFilter ?? "(all)"}";
    }

    /// <summary>Dump full details for a specific quest.</summary>
    public static string DumpQuest(string dbName)
    {
        if (Data == null) return "Data not initialized";

        var q = Data.GetByDBName(dbName);
        if (q == null) return $"Quest '{dbName}' not found";

        var lines = new System.Text.StringBuilder();
        lines.AppendLine($"DBName: {q.DBName}");
        lines.AppendLine($"Name: {q.DisplayName}");
        lines.AppendLine($"Type: {q.QuestType}");
        lines.AppendLine($"Zone: {q.ZoneContext}");
        lines.AppendLine($"Active: {State?.IsActive(dbName)}");
        lines.AppendLine($"Completed: {State?.IsCompleted(dbName)}");

        if (q.Steps != null)
        {
            lines.AppendLine($"Steps ({q.Steps.Count}):");
            foreach (var s in q.Steps)
                lines.AppendLine($"  {s.Order}. [{s.Action}] {s.Description}");
        }

        if (q.Rewards != null)
            lines.AppendLine($"Rewards: {q.Rewards.XP} XP, {q.Rewards.Gold} Gold, {q.Rewards.ItemName}");

        return lines.ToString();
    }

    /// <summary>Dump all quests for the current zone.</summary>
    public static string DumpZoneQuests()
    {
        if (Data == null || State == null) return "Not initialized";

        var zone = State.CurrentZone;
        var lines = new System.Text.StringBuilder();
        lines.AppendLine($"Quests in zone '{zone}':");

        foreach (var q in Data.All)
        {
            if (q.ZoneContext == null) continue;
            if (!q.ZoneContext.Equals(zone, System.StringComparison.OrdinalIgnoreCase)) continue;

            var status = State.IsCompleted(q.DBName) ? "done"
                       : State.IsActive(q.DBName) ? "active"
                       : "available";
            lines.AppendLine($"  [{status}] {q.DisplayName} ({q.DBName})");
        }

        return lines.ToString();
    }
}
