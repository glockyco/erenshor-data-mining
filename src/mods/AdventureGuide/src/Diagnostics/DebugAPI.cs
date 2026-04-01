using System.Diagnostics;
using System.Reflection;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
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
    internal static QuestResolutionService? Resolution { get; set; }
    internal static MarkerComputer? Markers { get; set; }
    internal static GameState? GameStateInstance { get; set; }

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
        sb.AppendLine($"Target: {explanation?.PrimaryText ?? "(none)"}");
        if (explanation != null)
            sb.AppendLine($"  TargetNode: {explanation.TargetIdentityText}");
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

    /// <summary>Profile resolving a single quest: cold (cache cleared) and hot timings.</summary>
    public static string ProfileQuestResolve(string name, int iterations = 5)
    {
        if (Graph == null || Resolution == null || State == null) return "Not initialized";

        var node = FindQuestNode(name);
        if (node == null) return $"Quest '{name}' not found";

        var bf = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
        var planCache = Resolution.GetType().GetField("_planCache", bf)?.GetValue(Resolution) as System.Collections.IDictionary;
        var projectionCache = Resolution.GetType().GetField("_planProjectionCache", bf)?.GetValue(Resolution) as System.Collections.IDictionary;
        var targetCache = Resolution.GetType().GetField("_targetCache", bf)?.GetValue(Resolution) as System.Collections.IDictionary;

        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"Profiling quest: {node.DisplayName} ({node.Key})");
        sb.AppendLine($"Iterations: {iterations}");
        sb.AppendLine();

        // Cold run (clear caches first)
        planCache?.Remove(node.Key);
        projectionCache?.Remove(node.Key);
        targetCache?.Remove(node.Key);
        var sw = Stopwatch.StartNew();
        var result = Resolution.ResolveQuest(node.Key);
        sw.Stop();
        sb.AppendLine($"Cold: {sw.Elapsed.TotalMilliseconds:F3} ms  targets={result.Targets.Count}");

        // Hot runs
        double totalHot = 0;
        for (int i = 0; i < iterations; i++)
        {
            sw.Restart();
            result = Resolution.ResolveQuest(node.Key);
            sw.Stop();
            double ms = sw.Elapsed.TotalMilliseconds;
            totalHot += ms;
            sb.AppendLine($"Hot[{i}]: {ms:F3} ms");
        }

        sb.AppendLine($"Hot avg: {totalHot / iterations:F3} ms");
        return sb.ToString();
    }

    /// <summary>Profile cold resolution of all actionable quests with aggregate stats.</summary>
    public static string ProfileActionableQuests()
    {
        if (Graph == null || Resolution == null || State == null) return "Not initialized";

        var bf = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
        var planCache = Resolution.GetType().GetField("_planCache", bf)?.GetValue(Resolution) as System.Collections.IDictionary;
        var projectionCache = Resolution.GetType().GetField("_planProjectionCache", bf)?.GetValue(Resolution) as System.Collections.IDictionary;
        var targetCache = Resolution.GetType().GetField("_targetCache", bf)?.GetValue(Resolution) as System.Collections.IDictionary;

        var sb = new System.Text.StringBuilder();
        sb.AppendLine("Profiling all actionable quests (cold):");
        sb.AppendLine();

        // Clear all caches
        planCache?.Clear();
        projectionCache?.Clear();
        targetCache?.Clear();

        int questCount = 0;
        double totalMs = 0;
        var sw = new Stopwatch();

        foreach (var node in Graph.NodesOfType(NodeType.Quest))
        {
            if (node.DbName == null) continue;
            if (!State.IsActionable(node.DbName)) continue;

            // Clear per-quest caches for a true cold measurement
            planCache?.Remove(node.Key);
            projectionCache?.Remove(node.Key);
            targetCache?.Remove(node.Key);

            sw.Restart();
            var result = Resolution.ResolveQuest(node.Key);
            sw.Stop();

            double ms = sw.Elapsed.TotalMilliseconds;
            totalMs += ms;
            questCount++;
            sb.AppendLine($"  {node.DisplayName}: {ms:F3} ms  targets={result.Targets.Count}");
        }

        if (questCount == 0) return "No active quests";

        sb.AppendLine();
        sb.AppendLine($"Total: {questCount} quests in {totalMs:F3} ms");
        sb.AppendLine($"Average: {totalMs / questCount:F3} ms/quest");
        return sb.ToString();
    }

    /// <summary>Profile MarkerComputer.Recompute() cold and hot.</summary>
    public static string ProfileMarkerRecompute(int iterations = 5)
    {
        if (Markers == null) return "Not initialized";

        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"Profiling MarkerComputer.Recompute()");
        sb.AppendLine($"Iterations: {iterations}");
        sb.AppendLine();

        // Cold run
        Markers.MarkDirty();
        var sw = Stopwatch.StartNew();
        Markers.Recompute();
        sw.Stop();
        sb.AppendLine($"Cold: {sw.Elapsed.TotalMilliseconds:F3} ms");

        // Hot runs
        double totalHot = 0;
        for (int i = 0; i < iterations; i++)
        {
            Markers.MarkDirty();
            sw.Restart();
            Markers.Recompute();
            sw.Stop();
            double ms = sw.Elapsed.TotalMilliseconds;
            totalHot += ms;
            sb.AppendLine($"Hot[{i}]: {ms:F3} ms");
        }

        sb.AppendLine($"Hot avg: {totalHot / iterations:F3} ms");
        return sb.ToString();
    }

    // ── Node-state classification ─────────────────────────────────────

    private static readonly NodeType[] SnapshotNodeTypes =
    {
        NodeType.Character, NodeType.SpawnPoint, NodeType.MiningNode,
        NodeType.ItemBag, NodeType.Door,
    };

    private static string ClassifyState(NodeState state) => state switch
    {
        SpawnAlive          => "alive",
        SpawnDead           => "dead",
        SpawnDisabled       => "disabled",
        SpawnNightLocked    => "night_locked",
        SpawnUnlockBlocked  => "unlock_blocked",
        MiningAvailable     => "mine_available",
        MiningMined         => "mine_mined",
        ItemBagAvailable    => "bag_available",
        ItemBagPickedUp     => "bag_picked_up",
        ItemBagGone         => "bag_gone",
        DoorUnlocked        => "door_unlocked",
        DoorLocked          => "door_locked",
        DoorClosed          => "door_closed",
        UnknownState        => "unknown",
        _                   => "unknown",
    };

    // ── Snapshot export ──────────────────────────────────────────────

    /// <summary>
    /// Capture a full pipeline-relevant state snapshot and write it to disk.
    /// Returns the output file path, or an error string if the mod is not initialized.
    /// </summary>
    public static string ExportStateSnapshot()
    {
        if (State == null || Graph == null || GameStateInstance == null)
            return "Not initialized";

        var zone = State.CurrentZone;

        // Keyring — private field, reflect once per call
        var keyringField = typeof(QuestStateTracker)
            .GetField("_keyringItemKeys", BindingFlags.NonPublic | BindingFlags.Instance);
        var keyring = keyringField?.GetValue(State) as HashSet<string>;

        // Live node states for resolver-registered types in current scene
        var liveStates = new Dictionary<string, LiveNodeState>();
        foreach (var nodeType in SnapshotNodeTypes)
        {
            foreach (var node in Graph.NodesOfType(nodeType))
            {
                if (!string.Equals(node.Scene, zone, StringComparison.OrdinalIgnoreCase))
                    continue;

                var ns = GameStateInstance.GetState(node.Key);
                liveStates[node.Key] = new LiveNodeState
                {
                    State = ClassifyState(ns),
                    IsSatisfied = ns.IsSatisfied,
                };
            }
        }

        var snapshot = new StateSnapshot
        {
            CapturedAt = DateTime.UtcNow.ToString("o"),
            CurrentZone = zone,
            ActiveQuests = new List<string>(State.ActiveQuests),
            CompletedQuests = new List<string>(State.CompletedQuests),
            Inventory = new Dictionary<string, int>(State.InventoryCounts),
            Keyring = keyring != null ? new List<string>(keyring) : new List<string>(),
            LiveNodeStates = liveStates,
        };

        var dir = Path.Combine(BepInEx.Paths.BepInExRootPath, "state-snapshots");
        Directory.CreateDirectory(dir);

        var timestamp = DateTime.UtcNow.ToString("yyyyMMdd_HHmmss");
        var filePath = Path.Combine(dir, $"{zone}_{timestamp}.json");

        var json = Newtonsoft.Json.JsonConvert.SerializeObject(snapshot, Newtonsoft.Json.Formatting.Indented);
        File.WriteAllText(filePath, json);

        return filePath;
    }
}
