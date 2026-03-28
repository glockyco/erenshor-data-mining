using AdventureGuide.Navigation;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Markers;

/// <summary>
/// Produces marker entries for all eligible quests. Does not render — MarkerSystem
/// (downstream) consumes the <see cref="Markers"/> list to place world markers.
/// </summary>
public sealed class MarkerComputer
{
    private readonly EntityGraph _graph;
    private readonly QuestStateTracker _tracker;
    private readonly GameState _state;
    private readonly QuestViewBuilder _viewBuilder;
    private readonly List<MarkerEntry> _markers = new();
    private bool _dirty = true;

    public IReadOnlyList<MarkerEntry> Markers => _markers;
    public bool IsDirty => _dirty;
    public int Version { get; private set; }

    public MarkerComputer(
        EntityGraph graph,
        QuestStateTracker tracker,
        GameState state,
        QuestViewBuilder viewBuilder)
    {
        _graph = graph;
        _tracker = tracker;
        _state = state;
        _viewBuilder = viewBuilder;
    }

    public void MarkDirty() => _dirty = true;

    /// <summary>
    /// Rebuild the full marker set if dirty. Clears and repopulates <see cref="Markers"/>
    /// by iterating every quest node and emitting markers based on quest state.
    /// </summary>
    public void Recompute()
    {
        if (!_dirty) return;
        _dirty = false;
        Version++;
        _markers.Clear();

        var quests = _graph.NodesOfType(NodeType.Quest);
        for (int i = 0; i < quests.Count; i++)
        {
            var quest = quests[i];
            if (string.IsNullOrEmpty(quest.DbName))
                continue;

            if (_tracker.IsCompleted(quest.DbName))
                continue;

            if (_tracker.IsActionable(quest.DbName))
                EmitActiveQuestMarkers(quest);
            else
                EmitQuestGiverMarkers(quest);
        }
    }

    /// <summary>
    /// Active/implicitly-active quest: emit objective markers for frontier nodes
    /// and turn-in markers for completed_by characters.
    /// </summary>
    private void EmitActiveQuestMarkers(Node quest)
    {
        // Build the view tree to feed the frontier computer.
        var root = _viewBuilder.Build(quest.Key);
        if (root != null)
        {
            var frontier = FrontierComputer.ComputeFrontier(root, _state);
            foreach (var nodeKey in frontier)
            {
                var node = _graph.GetNode(nodeKey);
                if (node == null) continue;
                // Quest nodes don't have world positions — skip them.
                if (node.Type == NodeType.Quest) continue;
                if (!HasPosition(node)) continue;

                var markerType = ResolveMarkerType(node);
                string? subText = markerType == MarkerType.Objective ? quest.DisplayName : null;

                _markers.Add(new MarkerEntry
                {
                    Type = markerType,
                    X = node.X!.Value,
                    Y = node.Y!.Value,
                    Z = node.Z!.Value,
                    Scene = node.Scene ?? "",
                    DisplayName = node.DisplayName,
                    SubText = subText ?? "",
                    NodeKey = node.Key,
                    QuestKey = quest.Key,
                });
            }
        }

        // Turn-in markers: show on the character that completes the quest.
        // Marker type depends on whether the player has all required items.
        var completedByEdges = _graph.OutEdges(quest.Key, EdgeType.CompletedBy);
        bool ready = AreRequiredItemsReady(quest.Key);

        for (int i = 0; i < completedByEdges.Count; i++)
        {
            var turnInNode = _graph.GetNode(completedByEdges[i].Target);
            if (turnInNode == null || !HasPosition(turnInNode)) continue;

            _markers.Add(new MarkerEntry
            {
                Type = ready ? MarkerType.TurnInReady : MarkerType.TurnInPending,
                X = turnInNode.X!.Value,
                Y = turnInNode.Y!.Value,
                Z = turnInNode.Z!.Value,
                Scene = turnInNode.Scene ?? "",
                DisplayName = turnInNode.DisplayName,
                SubText = quest.DisplayName,
                NodeKey = turnInNode.Key,
                QuestKey = quest.Key,
            });
        }
    }

    /// <summary>
    /// Not-started quest: emit quest giver markers for assigned_by characters.
    /// Prerequisite filtering will be refined later — for now all not-started quests qualify.
    /// </summary>
    private void EmitQuestGiverMarkers(Node quest)
    {
        var assignedByEdges = _graph.OutEdges(quest.Key, EdgeType.AssignedBy);
        for (int i = 0; i < assignedByEdges.Count; i++)
        {
            var giverNode = _graph.GetNode(assignedByEdges[i].Target);
            if (giverNode == null || !HasPosition(giverNode)) continue;

            _markers.Add(new MarkerEntry
            {
                Type = MarkerType.QuestGiver,
                X = giverNode.X!.Value,
                Y = giverNode.Y!.Value,
                Z = giverNode.Z!.Value,
                Scene = giverNode.Scene ?? "",
                DisplayName = giverNode.DisplayName,
                SubText = quest.DisplayName,
                NodeKey = giverNode.Key,
                QuestKey = quest.Key,
            });
        }
    }

    /// <summary>
    /// Check whether all items required by a quest are in the player's inventory.
    /// If the quest has no required items, returns true (nothing to wait for).
    /// </summary>
    private bool AreRequiredItemsReady(string questKey)
    {
        var edges = _graph.OutEdges(questKey, EdgeType.RequiresItem);
        if (edges.Count == 0) return true;

        for (int i = 0; i < edges.Count; i++)
        {
            var edge = edges[i];
            int required = edge.Quantity ?? 1;
            var itemState = _state.GetState(edge.Target);

            if (!(itemState is ItemCount ic) || ic.Count < required)
                return false;
        }

        return true;
    }

    private static bool HasPosition(Node node) =>
        node.X.HasValue && node.Y.HasValue && node.Z.HasValue;

    /// <summary>
    /// Determine the marker type for a frontier node based on its live state.
    /// Dead/respawning → DeadSpawn, night-locked → NightSpawn,
    /// quest-gated → QuestLocked, otherwise → Objective.
    /// </summary>
    private MarkerType ResolveMarkerType(Node node)
    {
        var nodeState = _state.GetState(node.Key);
        return nodeState switch
        {
            SpawnDead => MarkerType.DeadSpawn,
            SpawnNightLocked => MarkerType.NightSpawn,
            SpawnQuestGated => MarkerType.QuestLocked,
            SpawnDisabled => MarkerType.QuestLocked,
            MiningMined => MarkerType.DeadSpawn,
            _ => MarkerType.Objective,
        };
    }
}
