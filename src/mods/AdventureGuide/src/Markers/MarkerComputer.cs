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
    private readonly ViewNodePositionCollector _viewPositions;
    private readonly LiveStateTracker _liveState;

    // Output markers, deduplicated by spawn key.
    private readonly List<MarkerEntry> _markers = new();
    private readonly Dictionary<string, int> _markerIndex = new(StringComparer.Ordinal);
    private readonly List<ResolvedViewPosition> _detailedPositions = new();
    private bool _dirty = true;
    private int _lastLiveVersion = -1;

    /// <summary>Height offset above raw graph coordinates for static markers.</summary>
    private const float StaticHeightOffset = 2.5f;

    public IReadOnlyList<MarkerEntry> Markers => _markers;
    public int Version { get; private set; }

    public MarkerComputer(
        EntityGraph graph,
        QuestStateTracker tracker,
        GameState state,
        QuestViewBuilder viewBuilder,
        ViewNodePositionCollector viewPositions,
        LiveStateTracker liveState)
    {
        _graph = graph;
        _tracker = tracker;
        _state = state;
        _viewBuilder = viewBuilder;
        _viewPositions = viewPositions;
        _liveState = liveState;
    }

    public void MarkDirty() => _dirty = true;

    /// <summary>
    /// Rebuild the full marker set if dirty. Clears and repopulates <see cref="Markers"/>
    /// with one marker per spawn point, deduplicated by spawn key (highest-priority wins).
    /// </summary>
    public void Recompute()
    {
        if (_liveState.Version != _lastLiveVersion)
        {
            _dirty = true;
            _lastLiveVersion = _liveState.Version;
        }
        if (!_dirty) return;
        _dirty = false;
        Version++;
        _markers.Clear();
        _markerIndex.Clear();
        if (string.IsNullOrEmpty(_tracker.CurrentZone))
            return;
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
    /// Active or implicitly-active quests emit markers from the same resolved
    /// frontier targets that navigation and tracker use, but only keep targets
    /// in the player's current scene. This keeps markers truthful for nested
    /// crafting chains while avoiding world-wide marker work the player cannot see.
    /// </summary>
    private void EmitActiveQuestMarkers(Node quest)
    {
        var root = _viewBuilder.Build(quest.Key);
        if (root == null) return;

        var frontier = FrontierComputer.ComputeFrontier(root, _state);
        var emittedTargets = new HashSet<string>(StringComparer.Ordinal);

        for (int i = 0; i < frontier.Count; i++)
        {
            _detailedPositions.Clear();
            _viewPositions.CollectDetailed(frontier[i], _detailedPositions);

            for (int j = 0; j < _detailedPositions.Count; j++)
            {
                var resolved = _detailedPositions[j];
                if (!emittedTargets.Add(resolved.TargetNode.NodeKey))
                    continue;

                EmitResolvedMarker(quest, resolved);
            }
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
    private bool IsCurrentScene(string? scene) =>
        string.IsNullOrEmpty(scene)
        || string.Equals(scene, _tracker.CurrentZone, StringComparison.OrdinalIgnoreCase);

    private void EmitCharacterSpawnMarkers(
        Node charNode, Node quest, MarkerType questType, string questSubText)
    {
        var spawnEdges = _graph.OutEdges(charNode.Key, EdgeType.HasSpawn);

        if (spawnEdges.Count == 0)
        {
            // No spawn point edges — fall back to character node position (directly placed NPC).
            if (!HasPosition(charNode) || !IsCurrentScene(charNode.Scene)) return;

            var info = _liveState.GetCharacterState(charNode);
            EmitSpawnMarker(
                charNode.Key, charNode, quest, questType, questSubText,
                charNode.DisplayName, info);
            return;
        }

        for (int i = 0; i < spawnEdges.Count; i++)
        {
            var spawnNode = _graph.GetNode(spawnEdges[i].Target);
            if (spawnNode == null || !HasPosition(spawnNode) || !IsCurrentScene(spawnNode.Scene)) continue;

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
                // Permanently disabled (StopIfQuestComplete, scripted event, etc.)
                // Don't show a marker — no actionable information for the player.
                return;

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
            Y = positionNode.Y!.Value + StaticHeightOffset,
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
        if (!HasPosition(node) || !IsCurrentScene(node.Scene))
            return;

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
        else if (node.Type == NodeType.ItemBag)
        {
            var bagState = _liveState.GetItemBagState(node);
            if (bagState is ItemBagPickedUp picked)
            {
                type = MarkerType.DeadSpawn;
                actualSubText = $"{node.DisplayName}\n{FormatTimer(picked.RespawnSeconds)}";
            }
            else if (bagState is ItemBagGone)
            {
                return;
            }
        }

        TryAddMarker(new MarkerEntry
        {
            X = node.X!.Value,
            Y = node.Y!.Value + StaticHeightOffset,
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

    private void EmitResolvedMarker(Node quest, ResolvedViewPosition resolved)
    {
        if (!IsCurrentScene(resolved.Scene))
            return;

        var targetNode = resolved.TargetNode.Node;
        var explanation = NavigationExplanationBuilder.Build(resolved.GoalNode, resolved.TargetNode, _tracker);
        var markerType = DetermineActiveMarkerType(quest, resolved.GoalNode);
        var subText = FormatActiveMarkerSubText(explanation);

        if (targetNode.Type == NodeType.Character)
            EmitCharacterSpawnMarkers(targetNode, quest, markerType, subText);
        else if (HasPosition(targetNode))
            EmitStaticMarker(targetNode, quest, markerType, subText);
    }

    private static MarkerType DetermineActiveMarkerType(Node quest, ViewNode goalNode) =>
        goalNode.EdgeType == EdgeType.CompletedBy
            ? (quest.Repeatable ? MarkerType.TurnInRepeatReady : MarkerType.TurnInReady)
            : MarkerType.Objective;

    private static string FormatActiveMarkerSubText(NavigationExplanation explanation)
    {
        string action = ActionTextFormatter.FormatAction(
            explanation.TargetNode.EdgeType, explanation.TargetNode.Edge);
        string? reason = FormatActiveMarkerReason(explanation);
        if (string.IsNullOrEmpty(reason))
            return action;

        return action == reason ? action : $"{action}\n{reason}";
    }

    private static string? FormatActiveMarkerReason(NavigationExplanation explanation)
    {
        bool sameTarget = explanation.GoalNode.NodeKey == explanation.TargetNode.NodeKey
            && explanation.GoalNode.EdgeType == explanation.TargetNode.EdgeType;
        if (sameTarget)
            return null;

        if (explanation.GoalKind == NavigationGoalKind.CollectItem)
            return StripCollectPrefix(explanation.GoalText);

        return explanation.GoalText;
    }

    private static string StripCollectPrefix(string text)
    {
        const string prefix = "Collect ";
        return text.StartsWith(prefix, StringComparison.Ordinal)
            ? text.Substring(prefix.Length)
            : text;
    }

    // ── Text formatting ─────────────────────────────────────────────

    /// <summary>Format sub-text for quest giver markers based on assignment edge.</summary>
    private static string FormatAcquisitionText(Edge edge)
    {
        if (edge.Keyword != null)
            return $"Say '{edge.Keyword}'";
        return "Talk to";
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
