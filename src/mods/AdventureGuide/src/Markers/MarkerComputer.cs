using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Navigation;
using AdventureGuide.Resolution;
using AdventureGuide.Views;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.Markers;

/// <summary>
/// Scene-local world marker projection.
/// Quest semantics come from <see cref="QuestResolutionService"/> and immutable
/// graph blueprints; this class only materializes markers for the current scene.
/// </summary>
public sealed class MarkerComputer
{
    private const float StaticHeightOffset = 2.5f;

    private readonly EntityGraph _graph;
    private readonly GraphIndexes _indexes;
    private readonly QuestStateTracker _tracker;
    private readonly GameState _state;
    private readonly QuestResolutionService _resolution;
    private readonly LiveStateTracker _liveState;

    private readonly List<MarkerEntry> _markers = new();
    private readonly Dictionary<string, Dictionary<string, MarkerEntry>> _contributionsByNode = new(StringComparer.Ordinal);
    private readonly Dictionary<string, HashSet<string>> _nodesByQuest = new(StringComparer.Ordinal);
    private readonly HashSet<string> _pendingQuestKeys = new(StringComparer.Ordinal);

    private bool _dirty = true;
    private bool _fullRebuild = true;

    public IReadOnlyList<MarkerEntry> Markers => _markers;
    public int Version { get; private set; }

    public MarkerComputer(
        EntityGraph graph,
        GraphIndexes indexes,
        QuestStateTracker tracker,
        GameState state,
        QuestResolutionService resolution,
        LiveStateTracker liveState)
    {
        _graph = graph;
        _indexes = indexes;
        _tracker = tracker;
        _state = state;
        _resolution = resolution;
        _liveState = liveState;
    }

    public void ApplyGuideChangeSet(GuideChangeSet changeSet)
    {
        if (changeSet == null || !changeSet.HasMeaningfulChanges)
            return;

        var resolvedChangeSet = _resolution.ApplyChangeSet(changeSet);
        _dirty = true;

        if (resolvedChangeSet.SceneChanged)
        {
            _fullRebuild = true;
            _pendingQuestKeys.Clear();
            return;
        }

        foreach (var questKey in resolvedChangeSet.AffectedQuestKeys)
            _pendingQuestKeys.Add(questKey);
    }

    /// <summary>
    /// Fallback for live-world updates that do not currently produce structured
    /// quest deltas. Used by spawn/mining/item-bag patches.
    /// </summary>
    public void MarkDirty()
    {
        _dirty = true;
        _fullRebuild = true;
    }

    public void Recompute()
    {
        if (!_dirty)
            return;

        _dirty = false;

        if (string.IsNullOrEmpty(_tracker.CurrentZone))
        {
            ClearAll();
            PublishMarkers();
            return;
        }

        if (_fullRebuild)
        {
            RebuildCurrentScene();
            _fullRebuild = false;
            _pendingQuestKeys.Clear();
        }
        else
        {
            foreach (var questKey in _pendingQuestKeys)
                RebuildQuestMarkers(questKey);
            _pendingQuestKeys.Clear();
        }

        PublishMarkers();
    }

    private void RebuildCurrentScene()
    {
        ClearAll();

        var sceneQuestKeys = new HashSet<string>(StringComparer.Ordinal);
        foreach (var blueprint in _indexes.GetQuestGiversInScene(_tracker.CurrentZone))
            sceneQuestKeys.Add(blueprint.QuestKey);

        foreach (var questDbName in _tracker.GetActionableQuestDbNames())
        {
            var quest = _graph.GetQuestByDbName(questDbName);
            if (quest != null)
                sceneQuestKeys.Add(quest.Key);
        }

        foreach (var questKey in sceneQuestKeys)
            RebuildQuestMarkers(questKey);
    }

    private void RebuildQuestMarkers(string questKey)
    {
        RemoveQuestContributions(questKey);

        var quest = _graph.GetNode(questKey);
        if (quest == null || quest.Type != NodeType.Quest || string.IsNullOrEmpty(quest.DbName))
            return;

        if (_tracker.IsActionable(quest.DbName))
        {
            EmitActiveQuestMarkers(quest);
            return;
        }

        if (!_tracker.IsCompleted(quest.DbName) || quest.Repeatable)
            EmitQuestGiverMarkers(quest);
    }

    private void EmitActiveQuestMarkers(Node quest)
    {
        var resolution = _resolution.ResolveQuest(quest.Key);
        for (int i = 0; i < resolution.Frontier.Count; i++)
            EmitGoalMarkers(quest, resolution.Frontier[i], resolution.Frontier[i], new HashSet<string>(StringComparer.Ordinal));
    }

    private void EmitGoalMarkers(
        Node quest,
        ViewNode goalNode,
        ViewNode currentNode,
        HashSet<string> active)
    {
        if (currentNode.IsCycleRef)
            return;

        string token = string.Join("|", new[]
        {
            goalNode.NodeKey,
            currentNode.NodeKey,
            currentNode.EdgeType?.ToString() ?? "root",
        });
        if (!active.Add(token))
            return;

        try
        {
            if (currentNode.UnlockDependency != null)
            {
                EmitGoalMarkers(quest, currentNode.UnlockDependency, currentNode.UnlockDependency, active);
                return;
            }

            if (currentNode.Node.Type == NodeType.Quest && currentNode.NodeKey != goalNode.NodeKey)
            {
                var nested = _resolution.ResolveQuest(currentNode.NodeKey);
                for (int i = 0; i < nested.Frontier.Count; i++)
                    EmitGoalMarkers(quest, nested.Frontier[i], nested.Frontier[i], active);
                return;
            }

            if (currentNode.Node.Type is NodeType.Item or NodeType.Recipe)
            {
                bool hasReachableChild = false;
                for (int i = 0; i < currentNode.Children.Count; i++)
                {
                    if (!currentNode.Children[i].IsCycleRef && currentNode.Children[i].UnlockDependency == null)
                    {
                        hasReachableChild = true;
                        break;
                    }
                }

                for (int i = 0; i < currentNode.Children.Count; i++)
                {
                    var child = currentNode.Children[i];
                    if (hasReachableChild && child.UnlockDependency != null)
                        continue;

                    var childRole = ClassifyRole(child);
                    if (childRole == FrontierComputer.EdgeRole.Done)
                        continue;

                    var childGoalNode = childRole == FrontierComputer.EdgeRole.Source
                        ? goalNode
                        : child;
                    EmitGoalMarkers(quest, childGoalNode, child, active);
                }
                return;
            }

            EmitGoalLeafMarker(quest, goalNode, currentNode);
        }
        finally
        {
            active.Remove(token);
        }
    }

    private void EmitGoalLeafMarker(Node quest, ViewNode goalNode, ViewNode targetNode)
    {
        var explanation = NavigationExplanationBuilder.Build(goalNode, targetNode, _tracker, quest);
        var markerType = DetermineGoalMarkerType(quest, goalNode);
        var subText = FormatGoalMarkerSubText(explanation);

        if (targetNode.Node.Type == NodeType.Character)
        {
            EmitCharacterGoalMarkers(quest, targetNode.Node, markerType, subText);
            return;
        }

        if (!HasPosition(targetNode.Node) || !IsCurrentScene(targetNode.Node.Scene))
            return;

        var entry = CreateStaticMarkerEntry(
            quest.Key,
            targetNode.Node.Key,
            targetNode.Node.DisplayName,
            markerType,
            subText,
            targetNode.Node,
            targetNode.Node,
            new Vector3(targetNode.Node.X!.Value, targetNode.Node.Y!.Value, targetNode.Node.Z!.Value));
        if (entry != null)
            AddContribution(quest.Key, entry.NodeKey, entry);
    }

    private void EmitCharacterGoalMarkers(
        Node quest,
        Node characterNode,
        MarkerType markerType,
        string subText)
    {
        var spawnEdges = _graph.OutEdges(characterNode.Key, EdgeType.HasSpawn);
        if (spawnEdges.Count == 0)
        {
            if (!IsCurrentScene(characterNode.Scene))
                return;

            var directEntry = CreateCharacterMarkerEntry(
                quest.Key,
                characterNode.Key,
                characterNode.DisplayName,
                markerType,
                subText,
                characterNode,
                characterNode);
            if (directEntry != null)
                AddContribution(quest.Key, directEntry.NodeKey, directEntry);
            return;
        }

        for (int i = 0; i < spawnEdges.Count; i++)
        {
            var spawnNode = _graph.GetNode(spawnEdges[i].Target);
            if (spawnNode == null || !HasPosition(spawnNode) || !IsCurrentScene(spawnNode.Scene))
                continue;

            var entry = CreateCharacterMarkerEntry(
                quest.Key,
                spawnNode.Key,
                characterNode.DisplayName,
                markerType,
                subText,
                characterNode,
                spawnNode);
            if (entry != null)
                AddContribution(quest.Key, entry.NodeKey, entry);
        }
    }

    private static MarkerType DetermineGoalMarkerType(Node quest, ViewNode goalNode) =>
        goalNode.EdgeType == EdgeType.CompletedBy
            ? (quest.Repeatable ? MarkerType.TurnInRepeatReady : MarkerType.TurnInReady)
            : MarkerType.Objective;

    private static string FormatGoalMarkerSubText(NavigationExplanation explanation)
    {
        string action = ActionTextFormatter.FormatAction(
            explanation.TargetNode.EdgeType,
            explanation.TargetNode.Edge);
        string? reason = FormatGoalMarkerReason(explanation);
        if (string.IsNullOrEmpty(reason))
            return action;

        return action == reason ? action : $"{action}\n{reason}";
    }

    private static string? FormatGoalMarkerReason(NavigationExplanation explanation)
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

    private void EmitQuestGiverMarkers(Node quest)
    {
        var blueprints = _indexes.GetQuestGiversInScene(_tracker.CurrentZone);
        for (int i = 0; i < blueprints.Count; i++)
        {
            var blueprint = blueprints[i];
            if (blueprint.QuestKey != quest.Key)
                continue;

            var entry = CreateQuestGiverEntry(quest, blueprint);
            if (entry != null)
                AddContribution(quest.Key, entry.NodeKey, entry);
        }
    }

    private MarkerEntry? CreateQuestGiverEntry(Node quest, QuestGiverBlueprint blueprint)
    {
        var characterNode = _graph.GetNode(blueprint.CharacterKey);
        var positionNode = _graph.GetNode(blueprint.PositionNodeKey);
        if (characterNode == null || positionNode == null)
            return null;

        var (markerType, primaryLine) = ResolveQuestGiverPresentation(blueprint);
        string subText = $"{primaryLine}\n{blueprint.QuestDisplayName}";

        return CreateCharacterMarkerEntry(
            questKey: quest.Key,
            nodeKey: positionNode.Key,
            displayName: characterNode.DisplayName,
            markerType: markerType,
            subText: subText,
            targetNode: characterNode,
            positionNode: positionNode);
    }

    private (MarkerType Type, string PrimaryLine) ResolveQuestGiverPresentation(QuestGiverBlueprint blueprint)
    {
        string? blockedRequirement = FindFirstMissingRequirement(blueprint.RequiredQuestDbNames);
        if (blockedRequirement != null)
            return (MarkerType.QuestGiverBlocked, $"Requires: {blockedRequirement}");

        return (
            blueprint.Repeatable ? MarkerType.QuestGiverRepeat : MarkerType.QuestGiver,
            FormatInteraction(blueprint.Interaction));
    }

    private string? FindFirstMissingRequirement(IReadOnlyList<string> requiredQuestDbNames)
    {
        for (int i = 0; i < requiredQuestDbNames.Count; i++)
        {
            var dbName = requiredQuestDbNames[i];
            if (_tracker.IsCompleted(dbName))
                continue;

            var quest = _graph.GetQuestByDbName(dbName);
            return quest?.DisplayName ?? dbName;
        }

        return null;
    }

    private MarkerEntry? CreateActiveMarkerEntry(Node quest, ResolvedQuestTarget target)
    {
        var targetNode = target.TargetNode.Node;
        var positionNode = target.SourceKey != null
            ? _graph.GetNode(target.SourceKey)
            : targetNode;
        if (positionNode == null)
            return null;

        if (targetNode.Type == NodeType.Character)
        {
            return CreateCharacterMarkerEntry(
                quest.Key,
                positionNode.Key,
                targetNode.DisplayName,
                target.Marker.Type,
                target.Marker.SubText,
                targetNode,
                positionNode,
                target.Position);
        }

        return CreateStaticMarkerEntry(
            quest.Key,
            positionNode.Key,
            targetNode.DisplayName,
            target.Marker.Type,
            target.Marker.SubText,
            targetNode,
            positionNode,
            target.Position);
    }

    private MarkerEntry? CreateCharacterMarkerEntry(
        string questKey,
        string nodeKey,
        string displayName,
        MarkerType markerType,
        string subText,
        Node targetNode,
        Node positionNode,
        Vector3? fallbackPosition = null)
    {
        SpawnInfo info = positionNode.Type == NodeType.SpawnPoint || positionNode.IsDirectlyPlaced
            ? _liveState.GetSpawnState(positionNode)
            : _liveState.GetCharacterState(targetNode);

        if (info.State is SpawnDisabled)
            return null;

        var (type, text) = ResolveCharacterPresentation(displayName, markerType, subText, info);

        Vector3 position;
        if (TryGetMarkerPosition(positionNode, out var staticPosition))
        {
            position = staticPosition;
        }
        else if (fallbackPosition.HasValue)
        {
            position = fallbackPosition.Value;
        }
        else if (info.LiveNPC != null)
        {
            position = info.LiveNPC.transform.position;
        }
        else
        {
            return null;
        }

        string scene = positionNode.Scene
            ?? targetNode.Scene
            ?? _tracker.CurrentZone;

        return new MarkerEntry
        {
            X = position.x,
            Y = position.y + StaticHeightOffset,
            Z = position.z,
            Scene = scene,
            Type = type,
            DisplayName = displayName,
            SubText = text,
            NodeKey = nodeKey,
            QuestKey = questKey,
            LiveSpawnPoint = info.LiveSpawnPoint,
            TrackedNPC = info.LiveNPC,
            QuestType = markerType,
            QuestSubText = subText,
        };
    }

    private static (MarkerType Type, string SubText) ResolveCharacterPresentation(
        string displayName,
        MarkerType markerType,
        string subText,
        SpawnInfo info)
    {
        return info.State switch
        {
            SpawnAlive => (markerType, subText),
            SpawnDead dead => (MarkerType.DeadSpawn, $"{displayName}\n{FormatTimer(dead.RespawnSeconds)}"),
            SpawnNightLocked => (MarkerType.NightSpawn, BuildNightLockedText(displayName)),
            SpawnQuestGated gated => (MarkerType.QuestLocked, $"{displayName}\nRequires: {gated.QuestName}"),
            SpawnDisabled => (markerType, subText),
            _ => (markerType, subText),
        };
    }

    private MarkerEntry? CreateStaticMarkerEntry(
        string questKey,
        string nodeKey,
        string displayName,
        MarkerType markerType,
        string subText,
        Node targetNode,
        Node positionNode,
        Vector3 fallbackPosition)
    {
        var type = markerType;
        var text = subText;
        MiningNode? liveMining = null;

        if (targetNode.Type == NodeType.MiningNode)
        {
            var mining = _liveState.GetMiningState(targetNode);
            liveMining = mining.LiveNode;
            if (mining.State is MiningMined mined)
            {
                type = MarkerType.DeadSpawn;
                text = $"{displayName}\n{FormatTimer(mined.RespawnSeconds)}";
            }
        }
        else if (targetNode.Type == NodeType.ItemBag)
        {
            var bagState = _liveState.GetItemBagState(targetNode);
            if (bagState is ItemBagPickedUp picked)
            {
                type = MarkerType.DeadSpawn;
                text = $"{displayName}\n{FormatTimer(picked.RespawnSeconds)}";
            }
            else if (bagState is ItemBagGone)
            {
                return null;
            }
        }

        Vector3 position = TryGetMarkerPosition(positionNode, out var staticPosition)
            ? staticPosition
            : fallbackPosition;

        return new MarkerEntry
        {
            X = position.x,
            Y = position.y + StaticHeightOffset,
            Z = position.z,
            Scene = positionNode.Scene ?? targetNode.Scene ?? _tracker.CurrentZone,
            Type = type,
            DisplayName = displayName,
            SubText = text,
            NodeKey = nodeKey,
            QuestKey = questKey,
            LiveMiningNode = liveMining,
            QuestType = markerType,
            QuestSubText = subText,
        };
    }

    private void AddContribution(string questKey, string nodeKey, MarkerEntry entry)
    {
        if (!_contributionsByNode.TryGetValue(nodeKey, out var byQuest))
        {
            byQuest = new Dictionary<string, MarkerEntry>(StringComparer.Ordinal);
            _contributionsByNode[nodeKey] = byQuest;
        }

        byQuest[questKey] = entry;

        if (!_nodesByQuest.TryGetValue(questKey, out var nodes))
        {
            nodes = new HashSet<string>(StringComparer.Ordinal);
            _nodesByQuest[questKey] = nodes;
        }

        nodes.Add(nodeKey);
    }

    private void RemoveQuestContributions(string questKey)
    {
        if (!_nodesByQuest.TryGetValue(questKey, out var nodeKeys))
            return;

        foreach (var nodeKey in nodeKeys)
        {
            if (!_contributionsByNode.TryGetValue(nodeKey, out var byQuest))
                continue;

            byQuest.Remove(questKey);
            if (byQuest.Count == 0)
                _contributionsByNode.Remove(nodeKey);
        }

        _nodesByQuest.Remove(questKey);
    }

    private void PublishMarkers()
    {
        _markers.Clear();
        foreach (var byQuest in _contributionsByNode.Values)
        {
            MarkerEntry? best = null;
            foreach (var entry in byQuest.Values)
            {
                if (best == null || entry.Type < best.Type)
                    best = entry;
            }

            if (best != null)
                _markers.Add(CloneEntry(best));
        }

        Version++;
    }

    private void ClearAll()
    {
        _contributionsByNode.Clear();
        _nodesByQuest.Clear();
    }

    private bool IsCurrentScene(string? scene) =>
        string.IsNullOrEmpty(scene)
        || string.Equals(scene, _tracker.CurrentZone, StringComparison.OrdinalIgnoreCase);

    private static bool TryGetMarkerPosition(Node node, out Vector3 position)
    {
        if (node.X.HasValue && node.Y.HasValue && node.Z.HasValue)
        {
            position = new Vector3(node.X.Value, node.Y.Value, node.Z.Value);
            return true;
        }

        position = default;
        return false;
    }

    private static bool HasPosition(Node node) =>
        node.X.HasValue && node.Y.HasValue && node.Z.HasValue;


    private FrontierComputer.EdgeRole ClassifyRole(ViewNode node) =>
        FrontierComputer.ClassifyEdge(node, _state, _state.GetState(node.NodeKey));


    private static MarkerEntry CloneEntry(MarkerEntry entry) => new()
    {
        X = entry.X,
        Y = entry.Y,
        Z = entry.Z,
        Scene = entry.Scene,
        Type = entry.Type,
        DisplayName = entry.DisplayName,
        SubText = entry.SubText,
        NodeKey = entry.NodeKey,
        QuestKey = entry.QuestKey,
        LiveSpawnPoint = entry.LiveSpawnPoint,
        TrackedNPC = entry.TrackedNPC,
        LiveMiningNode = entry.LiveMiningNode,
        QuestType = entry.QuestType,
        QuestSubText = entry.QuestSubText,
    };

    private static string FormatInteraction(MarkerInteraction interaction) =>
        interaction.Kind == MarkerInteractionKind.SayKeyword && !string.IsNullOrEmpty(interaction.Keyword)
            ? $"Say '{interaction.Keyword}'"
            : "Talk to";

    private static string BuildNightLockedText(string displayName)
    {
        int hour = GameData.Time.GetHour();
        int min = GameData.Time.min;
        return $"{displayName}\nNight only (23:00-04:00)\nNow: {hour}:{min:D2}";
    }

    /// <summary>Format a respawn timer as ~M:SS or Respawning....</summary>
    internal static string FormatTimer(float seconds)
    {
        if (seconds <= 0f)
            return "Respawning...";

        int totalSeconds = (int)seconds;
        int minutes = totalSeconds / 60;
        int remainingSeconds = totalSeconds % 60;
        return $"~{minutes}:{remainingSeconds:D2}";
    }
}
