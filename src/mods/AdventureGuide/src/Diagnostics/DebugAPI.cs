using System.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Position;
using AdventureGuide.State;
using AdventureGuide.UI;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

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
    internal static CompiledGuideModel? Guide { get; set; }
    internal static QuestStateTracker? State { get; set; }
    internal static FilterState? Filter { get; set; }
    internal static NavigationEngine? Nav { get; set; }
    internal static NavigationTargetSelector? TargetSelector { get; set; }
    internal static GroundPathRenderer? GroundPath { get; set; }

    internal static ZoneRouter? Router { get; set; }
    internal static UnlockEvaluator? Unlocks { get; set; }
    internal static MarkerProjector? Markers { get; set; }

    internal static GameState? GameStateInstance { get; set; }

    internal static AdventureGuide.Resolution.NavigationTargetResolver? Resolver { get; set; }
    internal static AdventureGuide.State.GuideReader? Reader { get; set; }
    internal static DiagnosticsCore? Diagnostics { get; set; }
    internal static Func<MarkerDiagnosticsSnapshot>? MarkerSnapshot { get; set; }
    internal static Func<NavigationDiagnosticsSnapshot>? NavSnapshot { get; set; }
    internal static Func<TrackerDiagnosticsSnapshot>? TrackerSnapshot { get; set; }
    internal static Func<SpecTreeDiagnosticsSnapshot>? TreeSnapshot { get; set; }

    /// <summary>Dump current mod state: zone, active/completed counts, filter state.</summary>
    public static string DumpState()
    {
        if (State == null)
            return "Not initialized";

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
        if (Nav == null)
            return "Not initialized";
        if (!Nav.HasTarget)
            return "No active navigation target";

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

    /// <summary>Dump cached selector candidates for the current navigation target.</summary>
    public static string DumpNavCandidates()
    {
        if (Nav == null || TargetSelector == null)
            return "Not initialized";
        if (!Nav.HasTarget)
            return "No active navigation target";

        var playerPos = GameData.PlayerControl != null
            ? GameData.PlayerControl.transform.position
            : default(UnityEngine.Vector3);
        return TargetSelector.DumpCandidates(
            playerPos.x,
            playerPos.y,
            playerPos.z,
            Nav.CurrentScene,
            Nav.TargetNodeKey
        );
    }


    /// <summary>Dump full details for a specific quest by node key, DB name, or display name.</summary>
    public static string DumpQuest(string name)
    {
        if (Guide == null)
            return "Not initialized";

        var node = FindQuestNode(name);
        if (node == null)
            return $"Quest '{name}' not found";

        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"Key: {node.Key}");
        sb.AppendLine($"DbName: {node.DbName}");
        sb.AppendLine($"Name: {node.DisplayName}");
        sb.AppendLine($"Zone: {node.Zone}");
        sb.AppendLine($"Level: {node.Level}");
        sb.AppendLine($"Implicit: {node.Implicit}");
        sb.AppendLine($"Active: {State?.IsActive(node.DbName!)}");
        sb.AppendLine($"Completed: {State?.IsCompleted(node.DbName!)}");

        var edges = Guide.OutEdges(node.Key);
        sb.AppendLine($"Outgoing edges ({edges.Count}):");
        foreach (var e in edges)
            sb.AppendLine($"  [{e.Type}] > {e.Target}");

        return sb.ToString();
    }

    /// <summary>
    /// Run the resolution pipeline with tracing enabled and return
    /// a human-readable log of every decision. Accepts node key,
    /// DB name, or display name.
    /// </summary>
    public static string TraceQuest(string name)
    {
        if (Guide == null || Reader == null)
            return "Not initialized";

        var node = FindQuestNode(name);
        if (node == null)
            return $"Quest '{name}' not found";

        var tracer = new TextResolutionTracer();
        Reader.ReadQuestResolutionForTrace(node.Key, State?.CurrentZone ?? "", tracer);
        return tracer.GetTrace();
    }

    /// <summary>Dump all quests for the current zone.</summary>
    public static string DumpZoneQuests()
    {
        if (Guide == null || State == null)
            return "Not initialized";

        var zone = State.CurrentZone;
        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"Quests in zone '{zone}':");

        foreach (var node in Guide.NodesOfType(NodeType.Quest))
        {
            if (node.Zone == null)
                continue;
            if (!node.Zone.Equals(zone, StringComparison.OrdinalIgnoreCase))
                continue;

            var status =
                State.IsCompleted(node.DbName!) ? "done"
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
        if (Guide == null || State == null)
            return "Not initialized";

        var node = FindQuestNode(name);
        if (node == null)
            return $"Quest '{name}' not found";

        bool wasActive = GameData.HasQuest.Remove(node.DbName!);
        bool wasCompleted = GameData.CompletedQuests.Remove(node.DbName!);

        State.SyncFromGameData();

        string prev =
            wasActive ? "active"
            : wasCompleted ? "completed"
            : "not in quest log";
        return $"Reset '{node.DisplayName}' (was {prev})";
    }

    /// <summary>Test zone routing between two scenes.</summary>
    public static string TestRoute(string fromScene, string toScene)
    {
        if (Router == null)
            return "Not initialized";

        var route = Router.FindRoute(fromScene, toScene);
        if (route == null)
            return $"No route from {fromScene} to {toScene}";

        return $"NextHop={route.NextHopZoneKey} IsLocked={route.IsLocked} Path={string.Join(" > ", route.Path)}";
    }

    /// <summary>Dumps ZoneRouter adjacency graph and zone-key-to-scene mapping.</summary>
    public static string DumpZoneRouterAdj()
    {
        if (Router == null)
            return "Router is null";

        var sb = new System.Text.StringBuilder();

        sb.AppendLine("=== _zoneKeyToScene ===");
        foreach (var kvp in Router.DebugZoneKeyToScene)
            sb.AppendLine($"  {kvp.Key} -> {kvp.Value}");

        sb.AppendLine("=== _adj ===");
        foreach (var kvp in Router.DebugAdj)
        {
            sb.AppendLine($"  [{kvp.Key}]:");
            foreach (var edge in kvp.Value)
                sb.AppendLine(
                    $"    -> {edge.DestScene}  key={edge.ZoneLineKey}  accessible={edge.Accessible}"
                );
        }

        return sb.ToString();
    }

    /// <summary>Calls UnlockEvaluator.Evaluate for the given node key and returns the result.</summary>
    public static string DumpEntityUnlock(string nodeKey)
    {
        if (Unlocks == null)
            return "Unlocks are null";
        if (Guide == null)
            return "Guide is null";

        var node = Guide.GetNode(nodeKey);
        if (node == null)
            return $"Node '{nodeKey}' not found in guide";

        var eval = Unlocks.Evaluate(node);
        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"Node: {node.Key}  type={node.Type}  enabled={node.IsEnabled}");
        sb.AppendLine($"IsUnlocked: {eval.IsUnlocked}");
        sb.AppendLine($"Reason: {eval.Reason ?? "(none)"}");
        sb.AppendLine($"BlockingSources ({eval.BlockingSources.Count}):");
        foreach (var src in eval.BlockingSources)
            sb.AppendLine($"  {src.Key}  type={src.Type}");
        return sb.ToString();
    }

    private static Node? FindQuestNode(string name)
    {
        if (Guide == null)
            return null;

        var node = Guide.GetNode(name);
        if (node != null && node.Type == NodeType.Quest)
            return node;

        node = Guide.GetQuestByDbName(name);
        if (node != null)
            return node;

        foreach (var q in Guide.NodesOfType(NodeType.Quest))
        {
            if (string.Equals(q.DisplayName, name, StringComparison.OrdinalIgnoreCase))
                return q;
        }

        return null;
    }

    private static readonly NodeType[] SnapshotNodeTypes =
    {
        NodeType.Character,
        NodeType.SpawnPoint,
        NodeType.MiningNode,
        NodeType.ItemBag,
        NodeType.Door,
    };

    private static string ClassifyState(NodeState state) =>
        state switch
        {
            SpawnAlive => "alive",
            SpawnDead => "dead",
            SpawnDisabled => "disabled",
            SpawnNightLocked => "night_locked",
            SpawnUnlockBlocked => "unlock_blocked",
            MiningAvailable => "mine_available",
            MiningMined => "mine_mined",
            ItemBagAvailable => "bag_available",
            ItemBagPickedUp => "bag_picked_up",
            ItemBagGone => "bag_gone",
            DoorUnlocked => "door_unlocked",
            DoorLocked => "door_locked",
            DoorClosed => "door_closed",
            UnknownState => "unknown",
            _ => "unknown",
        };

    /// <summary>
    /// Dump timing statistics and incident state from the shared diagnostics core.
    /// </summary>
    public static string DumpPerfSummary() =>
        Diagnostics?.FormatRecentSummary() ?? "Not initialized";

    public static string DumpAllSpans()
    {
        if (Diagnostics == null)
            return "Not initialized";
        var spans = Diagnostics.GetRecentSpans();
        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"Recent spans ({spans.Count}):");
        foreach (var span in spans)
        {
            double ms = span.ElapsedTicks * 1000.0 / Stopwatch.Frequency;
            sb.AppendLine($"  {span.Kind} | {span.PrimaryKey} | {ms:F3} ms | v0={span.Value0} v1={span.Value1}");
        }
        return sb.ToString();
    }

    public static string DumpPerfReport() => DumpPerfSummary();

    public static string ProfileTrackedQuestRefresh()
    {
        if (NavSnapshot == null)
            return "Not initialized";

        var snapshot = NavSnapshot();
        var sb = new System.Text.StringBuilder();
        sb.AppendLine("Tracked quest refresh snapshot");
        sb.AppendLine($"Reason: {snapshot.LastForceReason}");
        sb.AppendLine($"Key count: {snapshot.LastBatchKeyCount}");

        sb.AppendLine($"Resolved targets: {snapshot.LastResolvedTargetCount}");
        if (snapshot.TopQuestCosts.Count > 0)
        {
            sb.AppendLine("Top quest costs:");
            foreach (var sample in snapshot.TopQuestCosts)
            {
                sb.AppendLine(
                    $"  {sample.QuestKey}: {(sample.ElapsedTicks * 1000.0 / Stopwatch.Frequency):F3} ms"
                );
            }
        }
        return sb.ToString().TrimEnd();
    }

    public static string ProfileDetailProjectionRefresh()
    {
        if (TreeSnapshot == null)
            return "Not initialized";

        var snapshot = TreeSnapshot();
        return string.Join(
            "\n",
            new[]
            {
                "Detail projection snapshot",
                $"Projected nodes: {snapshot.LastProjectedNodeCount}",
                $"Children: {snapshot.LastChildCount}",
                $"Pruned: {snapshot.LastPrunedCount}",
                $"Cycle prunes: {snapshot.LastCyclePruneCount}",
                $"Invalidated quests: {snapshot.LastInvalidatedQuestCount}",
                $"Full invalidation: {snapshot.LastInvalidationWasFull}",
            }
        );
    }

    /// <summary>
    /// Zero all diagnostics buffers so the next report reflects fresh data.
    /// </summary>

    public static string ResetPerfCounters()
    {
        if (Diagnostics == null)
            return "Not initialized";
        Diagnostics.ResetAll();
        return "Diagnostics counters reset.";
    }

    public static string DumpLastIncident() =>
        Diagnostics?.FormatLastIncidentSummary() ?? "Not initialized";

    public static string DumpLastIncidentDetailed() =>
        Diagnostics?.FormatDetailedLastIncident() ?? "Not initialized";

    public static string DumpAllIncidents() =>
        Diagnostics?.FormatAllIncidents() ?? "Not initialized";

    public static string CaptureIncidentNow()
    {
        if (Diagnostics == null)
            return "Not initialized";

        var snapshots = BuildSnapshots();
        var bundle = Diagnostics.CaptureNow(snapshots);
        return $"Captured {bundle.Incident.Kind} with {bundle.Spans.Count} spans and {bundle.Snapshots.Count} snapshots.";
    }

    /// <summary>
    /// Capture a full pipeline-relevant state snapshot and write it to disk.
    /// Returns the output file path, or an error string if the mod is not initialized.
    /// </summary>
    public static string ExportStateSnapshot()
    {
        if (State == null || Guide == null || GameStateInstance == null)
            return "Not initialized";

        var zone = State.CurrentZone;
        var keyring = State.KeyringItems;
        var liveStates = new Dictionary<string, LiveNodeState>();
        foreach (var nodeType in SnapshotNodeTypes)
        {
            foreach (var node in Guide.NodesOfType(nodeType))
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
            CapturedAt = DateTime.UtcNow.ToString("O"),
            CurrentZone = zone,
            ActiveQuests = State
                .ActiveQuests.OrderBy(q => q, StringComparer.OrdinalIgnoreCase)
                .ToList(),
            CompletedQuests = State
                .CompletedQuests.OrderBy(q => q, StringComparer.OrdinalIgnoreCase)
                .ToList(),
            Inventory = State
                .InventoryCounts.OrderBy(kv => kv.Key, StringComparer.OrdinalIgnoreCase)
                .ToDictionary(kv => kv.Key, kv => kv.Value),
            Keyring = keyring.OrderBy(k => k, StringComparer.OrdinalIgnoreCase).ToList(),
            LiveNodeStates = liveStates,
        };
        var dir = Path.Combine(BepInEx.Paths.BepInExRootPath, "state-snapshots");
        Directory.CreateDirectory(dir);

        var timestamp = DateTime.UtcNow.ToString("yyyyMMdd_HHmmss");
        var filePath = Path.Combine(dir, $"{zone}_{timestamp}.json");

        var json = Newtonsoft.Json.JsonConvert.SerializeObject(
            snapshot,
            Newtonsoft.Json.Formatting.Indented
        );
        File.WriteAllText(filePath, json);

        return filePath;
    }

    private static SnapshotEnvelope[] BuildSnapshots()
    {
        var snapshots = new List<SnapshotEnvelope>();
        if (MarkerSnapshot != null)
            snapshots.Add(SnapshotEnvelope.Create("marker", MarkerSnapshot()));
        if (NavSnapshot != null)
            snapshots.Add(SnapshotEnvelope.Create("navigation", NavSnapshot()));
        if (TrackerSnapshot != null)
            snapshots.Add(SnapshotEnvelope.Create("tracker", TrackerSnapshot()));
        if (TreeSnapshot != null)
            snapshots.Add(SnapshotEnvelope.Create("tree", TreeSnapshot()));
        return snapshots.ToArray();
    }
}
