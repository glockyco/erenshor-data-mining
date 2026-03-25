using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using AdventureGuide.UI;

namespace AdventureGuide.Diagnostics;

/// <summary>
/// Static API for runtime inspection via HotRepl.
/// All methods return human-readable strings for eval output.
///
/// Prefer these methods over raw reflection when inspecting AdventureGuide
/// from HotRepl. They avoid the cross-assembly type identity problems that
/// ScriptEngine's timestamp-suffixed assemblies create.
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
        if (State == null) return "State not initialized";

        return $"Zone: {State.CurrentZone}\n"
             + $"Active quests: {State.ActiveQuests.Count}\n"
             + $"Completed quests: {State.CompletedQuests.Count}\n"
             + $"Selected: {State.SelectedQuestDBName ?? "(none)"}\n"
             + $"Filter: {Filter?.FilterMode ?? QuestFilterMode.Active}\n"
             + $"Sort: {Filter?.SortMode ?? QuestSortMode.Alphabetical}\n"
             + $"Search: '{Filter?.SearchText ?? ""}'\n"
             + $"Zone filter: {Filter?.ZoneFilter ?? "(all)"}";
    }

    /// <summary>Dump navigation state: target, waypoint, distance, ground path.</summary>
    public static string DumpNav()
    {
        if (Nav == null) return "NavigationController not initialized";
        if (Nav.Target == null) return "No active navigation target";

        var t = Nav.Target;
        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"Target: {t.DisplayName}");
        sb.AppendLine($"  Kind: {t.TargetKind}");
        sb.AppendLine($"  Scene: {t.Scene}");
        sb.AppendLine($"  Position: {t.Position}");
        sb.AppendLine($"  SourceId: {t.SourceId ?? "(none)"}");
        sb.AppendLine($"  Quest: {t.QuestDBName} step {t.StepOrder}");

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

        return sb.ToString();
    }

    /// <summary>Dump entity registry state for a display name, or summary if null.</summary>
    public static string DumpEntities(string? displayName = null)
    {
        if (Entities == null) return "EntityRegistry not initialized";

        if (displayName != null)
        {
            // Accept either a stable key or a raw name (auto-prefix)
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
        if (Data == null) return "Data not initialized";

        // Try DB name first, then search by display name
        var q = Data.GetByDBName(name);
        if (q == null)
        {
            foreach (var entry in Data.All)
            {
                if (string.Equals(entry.DisplayName, name, System.StringComparison.OrdinalIgnoreCase))
                {
                    q = entry;
                    break;
                }
            }
        }
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

        // Resolve to DB name
        var q = Data.GetByDBName(name);
        if (q == null)
        {
            foreach (var entry in Data.All)
            {
                if (string.Equals(entry.DisplayName, name, System.StringComparison.OrdinalIgnoreCase))
                {
                    q = entry;
                    break;
                }
            }
        }
        if (q == null) return $"Quest '{name}' not found";

        bool wasActive = GameData.HasQuest.Remove(q.DBName);
        bool wasCompleted = GameData.CompletedQuests.Remove(q.DBName);

        // Sync tracker cache, then let nav re-evaluate
        State.SyncFromGameData();
        Nav?.OnGameStateChanged(State.CurrentZone);

        string prev = wasActive ? "active" : wasCompleted ? "completed" : "not in quest log";
        return $"Reset '{q.DisplayName}' (was {prev})";
    }


    /// <summary>Test zone graph routing between two scenes.</summary>
    public static string TestRoute(string fromScene, string toScene)
    {
        if (Nav == null) return "Nav not initialized";
        var graphField = typeof(NavigationController).GetField("_zoneGraph",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        var graph = graphField?.GetValue(Nav) as ZoneGraph;
        if (graph == null) return "ZoneGraph not found";
        var route = graph.FindRoute(fromScene, toScene);
        if (route == null) return $"No route from {fromScene} to {toScene}";
        return $"NextHop={route.NextHopZoneKey} IsLocked={route.IsLocked} Path={string.Join(" -> ", route.Path)}";
    }
}