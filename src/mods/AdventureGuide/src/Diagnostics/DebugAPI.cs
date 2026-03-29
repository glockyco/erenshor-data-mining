using AdventureGuide.Graph;
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
    internal static EntityGraph? Graph { get; set; }
    internal static QuestStateTracker? State { get; set; }
    internal static FilterState? Filter { get; set; }
    internal static NavigationEngine? Nav { get; set; }
    internal static EntityRegistry? Entities { get; set; }
    internal static GroundPathRenderer? GroundPath { get; set; }
    internal static ZoneRouter? Router { get; set; }

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

    /// <summary>Dump navigation state: target, position, distance, ground path.</summary>
    public static string DumpNav()
    {
        if (Nav == null) return "Not initialized";
        if (!Nav.HasTarget) return "No active navigation target";

        var sb = new System.Text.StringBuilder();
        var explanation = Nav.Explanation;
        sb.AppendLine($"Target: {explanation?.GoalText ?? "(none)"}");
        if (explanation != null)
            sb.AppendLine($"  TargetNode: {explanation.TargetText}");
        sb.AppendLine($"  NodeKey: {Nav.TargetNodeKey}");
        sb.AppendLine($"  Position: {Nav.EffectiveTarget}");
        sb.AppendLine($"  Distance: {Nav.Distance:F1}");
        sb.AppendLine($"  Scene: {Nav.CurrentScene}");

        if (GroundPath != null)
            sb.AppendLine($"GroundPath: enabled={GroundPath.Enabled}");

        return sb.ToString();
    }

    /// <summary>Dump entity registry state for a display name, or summary if null.</summary>
    public static string DumpEntities(string? displayName = null)
    {
        if (Entities == null) return "Not initialized";

        if (displayName != null)
        {
            string key = displayName.StartsWith("character:", StringComparison.OrdinalIgnoreCase)
                ? displayName
                : "character:" + displayName.Trim().ToLowerInvariant();
            int count = Entities.CountAlive(key);
            return $"{key}: {count} alive";
        }

        return "Pass a character name or stable key: DumpEntities(\"NPC Name\")";
    }

    /// <summary>Dump full details for a specific quest by node key, DB name, or display name.</summary>
    public static string DumpQuest(string name)
    {
        if (Graph == null) return "Not initialized";

        var node = FindQuestNode(name);
        if (node == null) return $"Quest '{name}' not found";

        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"Key: {node.Key}");
        sb.AppendLine($"DbName: {node.DbName}");
        sb.AppendLine($"Name: {node.DisplayName}");
        sb.AppendLine($"Zone: {node.Zone}");
        sb.AppendLine($"Level: {node.Level}");
        sb.AppendLine($"Implicit: {node.Implicit}");
        sb.AppendLine($"Active: {State?.IsActive(node.DbName!)}");
        sb.AppendLine($"Completed: {State?.IsCompleted(node.DbName!)}");

        var edges = Graph.OutEdges(node.Key);
        sb.AppendLine($"Outgoing edges ({edges.Count}):");
        foreach (var e in edges)
            sb.AppendLine($"  [{e.Type}] > {e.Target}");

        return sb.ToString();
    }

    /// <summary>Dump all quests for the current zone.</summary>
    public static string DumpZoneQuests()
    {
        if (Graph == null || State == null) return "Not initialized";

        var zone = State.CurrentZone;
        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"Quests in zone '{zone}':");

        foreach (var node in Graph.NodesOfType(NodeType.Quest))
        {
            if (node.Zone == null) continue;
            if (!node.Zone.Equals(zone, StringComparison.OrdinalIgnoreCase)) continue;

            var status = State.IsCompleted(node.DbName!) ? "done"
                       : State.IsActive(node.DbName!) ? "active"
                       : "available";
            sb.AppendLine($"  [{status}] {node.DisplayName} ({node.DbName})");
        }

        return sb.ToString();
    }

    /// <summary>
    /// Remove a quest from the player's active and completed lists so it
    /// can be accepted again. Accepts node key, DB name, or display name.
    /// Syncs the mod's cached state after modification.
    /// </summary>
    public static string ResetQuest(string name)
    {
        if (Graph == null || State == null) return "Not initialized";

        var node = FindQuestNode(name);
        if (node == null) return $"Quest '{name}' not found";

        bool wasActive = GameData.HasQuest.Remove(node.DbName!);
        bool wasCompleted = GameData.CompletedQuests.Remove(node.DbName!);

        State.SyncFromGameData();

        string prev = wasActive ? "active" : wasCompleted ? "completed" : "not in quest log";
        return $"Reset '{node.DisplayName}' (was {prev})";
    }

    /// <summary>Test zone routing between two scenes.</summary>
    public static string TestRoute(string fromScene, string toScene)
    {
        if (Router == null) return "Not initialized";

        var route = Router.FindRoute(fromScene, toScene);
        if (route == null) return $"No route from {fromScene} to {toScene}";

        return $"NextHop={route.NextHopZoneKey} IsLocked={route.IsLocked} Path={string.Join(" > ", route.Path)}";
    }

    private static Node? FindQuestNode(string name)
    {
        if (Graph == null) return null;

        // Try as node key first
        var node = Graph.GetNode(name);
        if (node != null && node.Type == NodeType.Quest) return node;

        // Try as DB name (O(1) via index)
        node = Graph.GetQuestByDbName(name);
        if (node != null) return node;

        // Last resort: display name (linear scan)
        foreach (var q in Graph.NodesOfType(NodeType.Quest))
        {
            if (string.Equals(q.DisplayName, name, StringComparison.OrdinalIgnoreCase))
                return q;
        }

        return null;
    }
}
