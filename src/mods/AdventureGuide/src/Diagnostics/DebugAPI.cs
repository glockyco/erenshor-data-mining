using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using AdventureGuide.UI;

namespace AdventureGuide.Diagnostics;

/// <summary>
/// Static API for runtime inspection via HotRepl.
/// All methods return human-readable strings for eval output.
///
/// Static fields are set by Plugin on startup and cleared on destroy.
/// HotRepl's evaluator auto-resets on ScriptEngine hot reload (F6),
/// resolving types from the newest assembly, so these fields always
/// point to the live Plugin's state.
/// </summary>
public static class DebugAPI
{
    internal static GuideData? Data { get; set; }
    internal static QuestStateTracker? State { get; set; }
    internal static FilterState? Filter { get; set; }
    internal static NavigationController? Nav { get; set; }
    internal static EntityRegistry? Entities { get; set; }
    internal static GroundPathRenderer? GroundPath { get; set; }

    /// <summary>Dump current mod state: zone, active/completed counts, filter state.</summary>
    public static string DumpState()
    {
        if (State == null) return "Not initialized";

        return $"Zone: {State.CurrentZone}\n"
             + $"Active quests: {State.ActiveQuests.Count}\n"
             + $"Completed quests: {State.CompletedQuests.Count}\n"
             + $"Selected: {State.SelectedQuestDBName ?? "(none)"}\n"
             + $"Filter: {Filter?.FilterMode}\n"
             + $"Sort: {Filter?.SortMode}\n"
             + $"Search: '{Filter?.SearchText ?? ""}'\n"
             + $"Zone filter: {Filter?.ZoneFilter ?? "(all)"}";
    }

    /// <summary>Dump navigation state: target, waypoint, distance, ground path.</summary>
    public static string DumpNav()
    {
        if (Nav == null) return "Not initialized";
        if (Nav.Target == null) return "No active navigation target";

        var t = Nav.Target;
        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"Target: {t.DisplayName}");
        sb.AppendLine($"  Kind: {t.TargetKind}");
        sb.AppendLine($"  Scene: {t.Scene}");
        sb.AppendLine($"  Position: {t.Position}");
        sb.AppendLine($"  SourceId: {t.SourceId ?? "(none)"}");
        sb.AppendLine($"  Quest: {t.QuestDBName} step {t.StepOrder}");
        sb.AppendLine($"  Origin: {t.OriginQuestDBName} step {t.OriginStepOrder}");

        var currentZone = State?.CurrentZone ?? "";
        sb.AppendLine($"  CrossZone: {t.IsCrossZone(currentZone)}");
        sb.AppendLine($"  Distance: {Nav.Distance:F1}");

        if (Nav.ZoneLineWaypoint != null)
        {
            var zl = Nav.ZoneLineWaypoint;
            sb.AppendLine($"ZoneLineWaypoint: {zl.DisplayName}");
            sb.AppendLine($"  Scene: {zl.Scene}");
            sb.AppendLine($"  Position: {zl.Position}");
        }
        else
        {
            sb.AppendLine("ZoneLineWaypoint: (none)");
        }

        if (GroundPath != null)
            sb.AppendLine($"GroundPath: enabled={GroundPath.Enabled}");

        sb.AppendLine($"ManualOverride: {Nav.IsManualSourceOverride}");

        return sb.ToString();
    }

    /// <summary>Dump entity registry state for a display name, or summary if null.</summary>
    public static string DumpEntities(string? displayName = null)
    {
        if (Entities == null) return "Not initialized";

        if (displayName != null)
        {
            string key = displayName.StartsWith("character:", System.StringComparison.OrdinalIgnoreCase)
                ? displayName
                : "character:" + displayName.Trim().ToLowerInvariant();
            int count = Entities.CountAlive(key);
            return $"{key}: {count} alive";
        }

        return "Pass a character name or stable key: DumpEntities(\"NPC Name\")";
    }

    /// <summary>Dump full details for a specific quest by DB name or display name.</summary>
    public static string DumpQuest(string name)
    {
        if (Data == null) return "Not initialized";

        var q = FindQuest(name);
        if (q == null) return $"Quest '{name}' not found (searched DB name and display name)";

        var lines = new System.Text.StringBuilder();
        lines.AppendLine($"DBName: {q.DBName}");
        lines.AppendLine($"Name: {q.DisplayName}");
        lines.AppendLine($"Type: {q.QuestType}");
        lines.AppendLine($"Zone: {q.ZoneContext}");
        lines.AppendLine($"Level: {q.LevelEstimate?.Recommended}");
        lines.AppendLine($"Active: {State?.IsActive(q.DBName)}");
        lines.AppendLine($"Completed: {State?.IsCompleted(q.DBName)}");

        if (q.Steps != null)
        {
            lines.AppendLine($"Steps ({q.Steps.Count}):");
            foreach (var s in q.Steps)
                lines.AppendLine($"  {s.Order}. [{s.Action}] {s.Description} (target_key={s.TargetKey})");
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

    /// <summary>
    /// Remove a quest from the player's active and completed lists so it
    /// can be accepted again. Accepts DB name or display name. Syncs the
    /// mod's cached state after modification.
    /// </summary>
    public static string ResetQuest(string name)
    {
        if (Data == null || State == null) return "Not initialized";

        var q = FindQuest(name);
        if (q == null) return $"Quest '{name}' not found";

        bool wasActive = GameData.HasQuest.Remove(q.DBName);
        bool wasCompleted = GameData.CompletedQuests.Remove(q.DBName);

        State.SyncFromGameData();
        Nav?.OnGameStateChanged(State.CurrentZone);

        string prev = wasActive ? "active" : wasCompleted ? "completed" : "not in quest log";
        return $"Reset '{q.DisplayName}' (was {prev})";
    }

    /// <summary>Test zone graph routing between two scenes.</summary>
    public static string TestRoute(string fromScene, string toScene)
    {
        if (Nav == null) return "Not initialized";
        var graphField = typeof(NavigationController).GetField("_zoneGraph",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        var graph = graphField?.GetValue(Nav) as ZoneGraph;
        if (graph == null) return "ZoneGraph not found";
        var route = graph.FindRoute(fromScene, toScene);
        if (route == null) return $"No route from {fromScene} to {toScene}";
        return $"NextHop={route.NextHopZoneKey} IsLocked={route.IsLocked} Path={string.Join(" -> ", route.Path)}";
    }

    private static QuestEntry? FindQuest(string name)
    {
        if (Data == null) return null;
        var q = Data.GetByDBName(name);
        if (q != null) return q;
        foreach (var entry in Data.All)
        {
            if (string.Equals(entry.DisplayName, name, System.StringComparison.OrdinalIgnoreCase))
                return entry;
        }
        return null;
    }
}
