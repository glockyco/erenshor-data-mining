using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Markers;

/// <summary>
/// Produces deduplicated marker entries for all eligible quests. Each character
/// is expanded to its individual spawn points via HasSpawn edges so every spawn
/// gets an independent marker with live state from <see cref="LiveStateTracker"/>.
///
/// Does not render — <see cref="MarkerSystem"/> consumes the output list.
/// </summary>
public sealed class MarkerComputer
{
    private readonly EntityGraph _graph;
    private readonly QuestStateTracker _tracker;
    private readonly GameState _state;
    private readonly QuestViewBuilder _viewBuilder;
    private readonly LiveStateTracker _liveState;

    // Output markers, deduplicated by spawn key.
    private readonly List<MarkerEntry> _markers = new();
    private readonly Dictionary<string, int> _markerIndex = new(StringComparer.Ordinal);
    private bool _dirty = true;

    public IReadOnlyList<MarkerEntry> Markers => _markers;
    public int Version { get; private set; }

    public MarkerComputer(
        EntityGraph graph,
        QuestStateTracker tracker,
        GameState state,
        QuestViewBuilder viewBuilder,
        LiveStateTracker liveState)
    {
        _graph = graph;
        _tracker = tracker;
        _state = state;
        _viewBuilder = viewBuilder;
        _liveState = liveState;
    }

    public void MarkDirty() => _dirty = true;

    /// <summary>
    /// Rebuild the full marker set if dirty. Clears and repopulates <see cref="Markers"/>
    /// with one marker per spawn point, deduplicated by spawn key (highest-priority wins).
    /// </summary>
    public void Recompute()
    {
        if (!_dirty) return;
        _dirty = false;
        Version++;
        _markers.Clear();
        _markerIndex.Clear();

        var quests = _graph.NodesOfType(NodeType.Quest);
        for (int i = 0; i < quests.Count; i++)
        {
            var quest = quests[i];
            if (string.IsNullOrEmpty(quest.DbName))
                continue;

            bool completed = _tracker.IsCompleted(quest.DbName);
            bool repeatable = quest.Repeatable;

            // Completed non-repeatable: no markers
            if (completed && !repeatable)
                continue;

            if (_tracker.IsActionable(quest.DbName))
                EmitActiveQuestMarkers(quest);
            else if (!completed || repeatable)
                EmitQuestGiverMarkers(quest, repeatable);
        }
    }

    // ── Active quest markers ────────────────────────────────────────────

    /// <summary>
    /// Active/implicitly-active quest: emit objective markers for frontier nodes
    /// (expanded to spawn points for characters), turn-in markers for completed_by
    /// characters, and item source markers for uncollected required items.
    /// </summary>
    private void EmitActiveQuestMarkers(Node quest)
    {
        var root = _viewBuilder.Build(quest.Key);
        if (root == null) return;

        var frontier = FrontierComputer.ComputeFrontier(root, _state);

        // Walk the view tree to find frontier nodes with their edge context.
        // We need the edge type and keyword to format action text.
        CollectFrontierMarkers(root, frontier, quest);

        // Turn-in markers on completed_by characters.
        EmitTurnInMarkers(quest);

        // Item source markers for items still needed.
        EmitItemSourceMarkers(quest);
    }

    /// <summary>
    /// Recursive walk of the view tree. For each node whose key is in the frontier,
    /// emit markers using the ViewNode's edge context for action text formatting.
    /// </summary>
    private void CollectFrontierMarkers(ViewNode node, HashSet<string> frontier, Node quest)
    {
        if (node.IsCycleRef) return;

        if (frontier.Contains(node.NodeKey))
        {
            var graphNode = node.Node;

            // Quest nodes and items without positions are not directly markable.
            // Items in the frontier are handled by EmitItemSourceMarkers instead.
            if (graphNode.Type == NodeType.Quest || graphNode.Type == NodeType.Item)
            {
                // Don't return — still recurse into children for nested frontier nodes
            }
            else if (graphNode.Type == NodeType.Character)
            {
                string subText = FormatStepActionText(node.EdgeType, node.Edge);
                EmitCharacterSpawnMarkers(
                    graphNode, quest, MarkerType.Objective, subText);
            }
            else if (HasPosition(graphNode))
            {
                // Mining nodes, item bags, waters, forges, etc. — emit at static position
                EmitStaticMarker(graphNode, quest, MarkerType.Objective,
                    FormatStepActionText(node.EdgeType, node.Edge));
            }
        }

        for (int i = 0; i < node.Children.Count; i++)
            CollectFrontierMarkers(node.Children[i], frontier, quest);
    }

    // ── Turn-in markers ─────────────────────────────────────────────────

    private void EmitTurnInMarkers(Node quest)
    {
        var edges = _graph.OutEdges(quest.Key, EdgeType.CompletedBy);
        if (edges.Count == 0) return;

        bool ready = AreRequiredItemsReady(quest.Key);
        bool repeatable = quest.Repeatable;

        MarkerType markerType;
        if (ready)
            markerType = repeatable ? MarkerType.TurnInRepeatReady : MarkerType.TurnInReady;
        else
            markerType = MarkerType.TurnInPending;

        for (int i = 0; i < edges.Count; i++)
        {
            var edge = edges[i];
            var charNode = _graph.GetNode(edge.Target);
            if (charNode == null) continue;

            string subText = FormatTurnInText(quest, edge);
            EmitCharacterSpawnMarkers(charNode, quest, markerType, subText);
        }
    }

    // ── Item source markers ─────────────────────────────────────────────

    /// <summary>
    /// For each required item the player doesn't yet have enough of, emit
    /// markers on all source characters (drop, sell, give) expanded to spawn points.
    /// Sub-text shows collection progress: "2/5 Dragon Scale".
    /// </summary>
    private void EmitItemSourceMarkers(Node quest)
    {
        var reqEdges = _graph.OutEdges(quest.Key, EdgeType.RequiresItem);
        for (int i = 0; i < reqEdges.Count; i++)
        {
            var reqEdge = reqEdges[i];
            int required = reqEdge.Quantity ?? 1;
            int have = CountItemByKey(reqEdge.Target);
            if (have >= required) continue;

            var itemNode = _graph.GetNode(reqEdge.Target);
            if (itemNode == null) continue;

            string progress = $"{have}/{required} {itemNode.DisplayName}";

            // Find all source characters via reverse edges (DropsItem, SellsItem, GivesItem, YieldsItem)
            EmitItemSourcesForNode(itemNode, quest, progress);
        }
    }

    /// <summary>
    /// Emit markers for all sources of an item node: characters that drop/sell/give it,
    /// mining nodes that yield it, item bags that contain it.
    /// </summary>
    private void EmitItemSourcesForNode(Node itemNode, Node quest, string progress)
    {
        // Characters: DropsItem, SellsItem, GivesItem are character→item edges.
        // We need in-edges on the item to find the source characters.
        var inEdges = _graph.InEdges(itemNode.Key);
        for (int i = 0; i < inEdges.Count; i++)
        {
            var edge = inEdges[i];
            if (edge.Type != EdgeType.DropsItem
                && edge.Type != EdgeType.SellsItem
                && edge.Type != EdgeType.GivesItem)
                continue;

            var sourceNode = _graph.GetNode(edge.Source);
            if (sourceNode == null) continue;

            if (sourceNode.Type == NodeType.Character)
            {
                EmitCharacterSpawnMarkers(sourceNode, quest, MarkerType.Objective, progress);
            }
            else if (HasPosition(sourceNode))
            {
                EmitStaticMarker(sourceNode, quest, MarkerType.Objective, progress);
            }
        }

        // Mining nodes / item bags: YieldsItem, Contains are source→item edges.
        // We need in-edges on the item to find them.
        for (int i = 0; i < inEdges.Count; i++)
        {
            var edge = inEdges[i];
            if (edge.Type != EdgeType.YieldsItem && edge.Type != EdgeType.Contains)
                continue;

            var sourceNode = _graph.GetNode(edge.Source);
            if (sourceNode == null || !HasPosition(sourceNode)) continue;

            EmitStaticMarker(sourceNode, quest, MarkerType.Objective, progress);
        }
    }

    // ── Quest giver markers ─────────────────────────────────────────────

    /// <summary>
    /// Not-started quest: emit quest giver markers for assigned_by characters,
    /// expanded to spawn points.
    /// </summary>
    private void EmitQuestGiverMarkers(Node quest, bool repeatable)
    {
        // Check prerequisites: any RequiresQuest edge pointing to an incomplete quest blocks the giver
        var prereqEdges = _graph.OutEdges(quest.Key, EdgeType.RequiresQuest);
        MarkerType markerType;
        string? prereqOverrideSubText = null;
        bool blocked = false;

        for (int i = 0; i < prereqEdges.Count; i++)
        {
            var prereqNode = _graph.GetNode(prereqEdges[i].Target);
            if (prereqNode == null) continue;
            if (prereqNode.DbName != null && _tracker.IsCompleted(prereqNode.DbName)) continue;
            // This prerequisite is not complete — quest giver is blocked
            blocked = true;
            prereqOverrideSubText = $"Requires: {prereqNode.DisplayName}";
            break;
        }

        if (blocked)
            markerType = MarkerType.QuestGiverBlocked;
        else
            markerType = repeatable ? MarkerType.QuestGiverRepeat : MarkerType.QuestGiver;

        var edges = _graph.OutEdges(quest.Key, EdgeType.AssignedBy);
        for (int i = 0; i < edges.Count; i++)
        {
            var edge = edges[i];
            var charNode = _graph.GetNode(edge.Target);
            if (charNode == null) continue;

            string subText = prereqOverrideSubText ?? FormatAcquisitionText(edge);
            EmitCharacterSpawnMarkers(charNode, quest, markerType, subText);
        }
    }

    // ── Per-spawn-point expansion ───────────────────────────────────────

    /// <summary>
    /// Iterate all spawn points for a character via HasSpawn edges. For each spawn
    /// point, query <see cref="LiveStateTracker"/> for live state and emit the
    /// appropriate marker: quest marker when alive, absence marker when not.
    /// </summary>
    private void EmitCharacterSpawnMarkers(
        Node charNode, Node quest, MarkerType questType, string questSubText)
    {
        var spawnEdges = _graph.OutEdges(charNode.Key, EdgeType.HasSpawn);

        if (spawnEdges.Count == 0)
        {
            // No spawn point edges — fall back to character node position (directly placed NPC).
            if (!HasPosition(charNode)) return;

            var info = _liveState.GetCharacterState(charNode);
            EmitSpawnMarker(
                charNode.Key, charNode, quest, questType, questSubText,
                charNode.DisplayName, info);
            return;
        }

        for (int i = 0; i < spawnEdges.Count; i++)
        {
            var spawnNode = _graph.GetNode(spawnEdges[i].Target);
            if (spawnNode == null || !HasPosition(spawnNode)) continue;

            var info = _liveState.GetSpawnState(spawnNode);
            EmitSpawnMarker(
                spawnNode.Key, spawnNode, quest, questType, questSubText,
                charNode.DisplayName, info);
        }
    }

    /// <summary>
    /// Emit a single marker for a spawn point (or character fallback), choosing
    /// the marker type and sub-text based on live state.
    /// </summary>
    private void EmitSpawnMarker(
        string nodeKey, Node positionNode, Node quest,
        MarkerType questType, string questSubText,
        string displayName, SpawnInfo info)
    {
        MarkerType type;
        string subText;

        switch (info.State)
        {
            case SpawnAlive:
                type = questType;
                subText = questSubText;
                break;

            case SpawnDead dead:
                type = MarkerType.DeadSpawn;
                subText = $"{displayName}\n{FormatTimer(dead.RespawnSeconds)}";
                break;

            case SpawnNightLocked:
                type = MarkerType.NightSpawn;
                int hour = GameData.Time.GetHour();
                int min = GameData.Time.min;
                subText = $"{displayName}\nNight only (23:00-04:00)\nNow: {hour}:{min:D2}";
                break;

            case SpawnQuestGated gated:
                type = MarkerType.QuestLocked;
                subText = $"{displayName}\nRequires: {gated.QuestName}";
                break;

            case SpawnDisabled:
                type = MarkerType.QuestLocked;
                subText = $"{displayName}\nRequires quest unlock";
                break;

            default:
                // Unknown state (spawn not found in scene) — still emit at static position
                // so players see something. Use quest marker type.
                type = questType;
                subText = questSubText;
                break;
        }

        TryAddMarker(new MarkerEntry
        {
            X = positionNode.X!.Value,
            Y = positionNode.Y!.Value,
            Z = positionNode.Z!.Value,
            Scene = positionNode.Scene ?? "",
            Type = type,
            DisplayName = displayName,
            SubText = subText,
            NodeKey = nodeKey,
            QuestKey = quest.Key,
            LiveSpawnPoint = info.LiveSpawnPoint,
            TrackedNPC = info.LiveNPC,
            QuestType = questType,
            QuestSubText = questSubText,
        });
    }

    /// <summary>
    /// Emit a marker at a static node position (mining node, item bag, water, forge, etc.).
    /// No per-spawn expansion — these nodes have fixed world positions.
    /// </summary>
    private void EmitStaticMarker(Node node, Node quest, MarkerType questType, string subText)
    {
        MarkerType type = questType;
        string actualSubText = subText;
        MiningNode? liveMining = null;

        // Check live state for mining nodes
        if (node.Type == NodeType.MiningNode)
        {
            var miningInfo = _liveState.GetMiningState(node);
            liveMining = miningInfo.LiveNode;

            if (miningInfo.State is MiningMined mined)
            {
                type = MarkerType.DeadSpawn;
                actualSubText = $"{node.DisplayName}\n{FormatTimer(mined.RespawnSeconds)}";
            }
        }

        TryAddMarker(new MarkerEntry
        {
            X = node.X!.Value,
            Y = node.Y!.Value,
            Z = node.Z!.Value,
            Scene = node.Scene ?? "",
            Type = type,
            DisplayName = node.DisplayName,
            SubText = actualSubText,
            NodeKey = node.Key,
            QuestKey = quest.Key,
            LiveMiningNode = liveMining,
            QuestType = questType,
            QuestSubText = subText,
        });
    }

    // ── Deduplication ───────────────────────────────────────────────────

    /// <summary>
    /// Add a marker, deduplicating by node key. When multiple quests reference
    /// the same spawn point, the highest-priority marker type wins (lower enum
    /// ordinal = higher priority).
    /// </summary>
    private void TryAddMarker(MarkerEntry entry)
    {
        if (_markerIndex.TryGetValue(entry.NodeKey, out int existingIdx))
        {
            var existing = _markers[existingIdx];
            if (entry.Type < existing.Type)
                _markers[existingIdx] = entry;
            return;
        }

        _markerIndex[entry.NodeKey] = _markers.Count;
        _markers.Add(entry);
    }

    // ── Text formatting ─────────────────────────────────────────────────

    /// <summary>Format sub-text for step targets based on edge type and keyword.</summary>
    private static string FormatStepActionText(EdgeType? edgeType, Edge? edge)
    {
        return edgeType switch
        {
            EdgeType.StepTalk when edge?.Keyword != null => $"Say '{edge.Keyword}'",
            EdgeType.StepTalk => "Talk to",
            EdgeType.StepKill when edge?.Quantity is > 1 => $"Kill ({edge.Quantity})",
            EdgeType.StepKill => "Kill",
            EdgeType.StepShout when edge?.Keyword != null => $"Shout '{edge.Keyword}'",
            EdgeType.StepShout => "Shout near",
            EdgeType.StepTravel => "Travel to",
            EdgeType.StepRead => "Read",
            _ => "Talk to",
        };
    }

    /// <summary>Format sub-text for quest giver markers based on assignment edge.</summary>
    private static string FormatAcquisitionText(Edge edge)
    {
        if (edge.Keyword != null)
            return $"Say '{edge.Keyword}'";
        return "Talk to";
    }

    /// <summary>Format sub-text for turn-in markers: "Give {item}" or "Say '{kw}'".</summary>
    private string FormatTurnInText(Node quest, Edge completedByEdge)
    {
        // If the completion edge has a keyword, that's what the player says
        if (completedByEdge.Keyword != null)
            return $"Say '{completedByEdge.Keyword}'";

        // Otherwise, format based on required items
        var reqEdges = _graph.OutEdges(quest.Key, EdgeType.RequiresItem);
        if (reqEdges.Count == 0)
            return "Talk to";

        if (reqEdges.Count == 1)
        {
            var itemNode = _graph.GetNode(reqEdges[0].Target);
            return itemNode != null ? $"Give {itemNode.DisplayName}" : "Give item";
        }

        return $"Give {reqEdges.Count} items";
    }

    // ── Helpers ──────────────────────────────────────────────────────────

    private bool AreRequiredItemsReady(string questKey)
    {
        var edges = _graph.OutEdges(questKey, EdgeType.RequiresItem);
        if (edges.Count == 0) return true;

        for (int i = 0; i < edges.Count; i++)
        {
            int required = edges[i].Quantity ?? 1;
            int have = CountItemByKey(edges[i].Target);
            if (have < required) return false;
        }

        return true;
    }

    /// <summary>
    /// Count items by item node key. Translates node key to stable key for
    /// QuestStateTracker.CountItem (which expects "item:name" format — the
    /// same format used as the node key).
    /// </summary>
    private int CountItemByKey(string itemNodeKey)
    {
        return _tracker.CountItem(itemNodeKey);
    }

    private static bool HasPosition(Node node) =>
        node.X.HasValue && node.Y.HasValue && node.Z.HasValue;

    /// <summary>Format a respawn timer as "~M:SS" or "Respawning...".</summary>
    internal static string FormatTimer(float seconds)
    {
        if (seconds <= 0f) return "Respawning...";
        int totalSeconds = (int)seconds;
        int m = totalSeconds / 60;
        int s = totalSeconds % 60;
        return $"~{m}:{s:D2}";
    }
}
