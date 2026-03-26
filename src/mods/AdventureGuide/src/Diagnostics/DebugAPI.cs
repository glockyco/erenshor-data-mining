using System.Reflection;
using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using AdventureGuide.UI;
using UnityEngine;

namespace AdventureGuide.Diagnostics;

/// <summary>
/// Static API for runtime inspection via HotRepl.
/// All methods return human-readable strings for eval output.
///
/// Resolves the live Plugin instance via type-name matching on each call,
/// so it works correctly after F6 hot reload (which creates a new assembly
/// with a timestamp suffix). No static field wiring from Plugin needed.
/// </summary>
public static class DebugAPI
{
    private const string PluginTypeName = "AdventureGuide.Plugin";
    private const BindingFlags BF = BindingFlags.NonPublic | BindingFlags.Instance;

    // Cached reflection state — invalidated when the plugin instance changes
    // (hot reload creates a new instance with a different Type).
    private static MonoBehaviour? _cachedPlugin;
    private static System.Type? _cachedType;
    private static FieldInfo? _fData, _fState, _fNav, _fEntities, _fGroundPath, _fWindow;

    private static MonoBehaviour? FindPlugin()
    {
        // Check if cached instance is still alive (Unity fake-null safe)
        if (_cachedPlugin != null && !ReferenceEquals(_cachedPlugin, null))
            return _cachedPlugin;

        // Scan all MonoBehaviours for the live Plugin by type name.
        // Uses non-generic FindObjectsOfTypeAll to avoid type resolution
        // issues with ILRepack-merged assemblies.
        foreach (var obj in Resources.FindObjectsOfTypeAll(typeof(MonoBehaviour)))
        {
            if (obj != null && obj.GetType().FullName == PluginTypeName)
            {
                var mb = (MonoBehaviour)obj;
                CacheReflection(mb);
                return _cachedPlugin = mb;
            }
        }

        _cachedPlugin = null;
        _cachedType = null;
        return null;
    }

    private static void CacheReflection(MonoBehaviour plugin)
    {
        var t = plugin.GetType();
        if (t == _cachedType) return;
        _cachedType = t;
        _fData = t.GetField("_data", BF);
        _fState = t.GetField("_state", BF);
        _fNav = t.GetField("_nav", BF);
        _fEntities = t.GetField("_entities", BF);
        _fGroundPath = t.GetField("_groundPath", BF);
        _fWindow = t.GetField("_window", BF);
    }

    private static T? Get<T>(FieldInfo? field) where T : class
    {
        var plugin = FindPlugin();
        if (plugin == null || field == null) return null;
        return field.GetValue(plugin) as T;
    }

    // Convenience accessors — each call resolves through the live plugin
    private static GuideData? Data => Get<GuideData>(_fData);
    private static QuestStateTracker? State => Get<QuestStateTracker>(_fState);
    private static NavigationController? Nav => Get<NavigationController>(_fNav);
    private static EntityRegistry? Entities => Get<EntityRegistry>(_fEntities);
    private static GroundPathRenderer? GroundPath => Get<GroundPathRenderer>(_fGroundPath);
    private static FilterState? Filter
    {
        get
        {
            var plugin = FindPlugin();
            if (plugin == null || _fWindow == null) return null;
            var window = _fWindow.GetValue(plugin);
            if (window == null) return null;
            var filterProp = window.GetType().GetProperty("Filter");
            return filterProp?.GetValue(window) as FilterState;
        }
    }

    /// <summary>Dump current mod state: zone, active/completed counts, filter state.</summary>
    public static string DumpState()
    {
        if (State == null) return "Plugin not found";

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
        if (Nav == null) return "Plugin not found";
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

        // Multi-source state
        sb.AppendLine($"ManualOverride: {Nav.IsManualSourceOverride}");

        return sb.ToString();
    }

    /// <summary>Dump entity registry state for a display name, or summary if null.</summary>
    public static string DumpEntities(string? displayName = null)
    {
        if (Entities == null) return "Plugin not found";

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
        if (Data == null) return "Plugin not found";

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
        if (Data == null || State == null) return "Plugin not found";

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
        if (Data == null || State == null) return "Plugin not found";

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

        State.SyncFromGameData();
        Nav?.OnGameStateChanged(State.CurrentZone);

        string prev = wasActive ? "active" : wasCompleted ? "completed" : "not in quest log";
        return $"Reset '{q.DisplayName}' (was {prev})";
    }

    /// <summary>Test zone graph routing between two scenes.</summary>
    public static string TestRoute(string fromScene, string toScene)
    {
        if (Nav == null) return "Plugin not found";
        var graphField = typeof(NavigationController).GetField("_zoneGraph", BF);
        var graph = graphField?.GetValue(Nav) as ZoneGraph;
        if (graph == null) return "ZoneGraph not found";
        var route = graph.FindRoute(fromScene, toScene);
        if (route == null) return $"No route from {fromScene} to {toScene}";
        return $"NextHop={route.NextHopZoneKey} IsLocked={route.IsLocked} Path={string.Join(" -> ", route.Path)}";
    }
}
