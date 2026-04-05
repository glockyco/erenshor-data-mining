using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Resolution;
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
    private readonly QuestResolutionService _resolution;
    private readonly LiveStateTracker _liveState;
    private readonly NavigationSet _navSet;
    private readonly TrackerState _trackerState;

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
        QuestResolutionService resolution,
        LiveStateTracker liveState,
        NavigationSet navSet,
        TrackerState trackerState)
    {
        _graph = graph;
        _indexes = indexes;
        _tracker = tracker;
        _resolution = resolution;
        _liveState = liveState;
        _navSet = navSet;
        _trackerState = trackerState;

        _navSet.Changed += OnExternalSelectionChanged;
        _trackerState.Tracked += OnTrackedChanged;
        _trackerState.Untracked += OnTrackedChanged;
    }

    public void Destroy()
    {
        _navSet.Changed -= OnExternalSelectionChanged;
        _trackerState.Tracked -= OnTrackedChanged;
        _trackerState.Untracked -= OnTrackedChanged;
    }

    private void OnExternalSelectionChanged() => MarkDirty();
    private void OnTrackedChanged(string _) => MarkDirty();

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

        // Include quests the player explicitly selected as NAV targets or
        // pinned to the tracker, even if they are not in the quest log.
        foreach (var nodeKey in _navSet.Keys)
        {
            var node = _graph.GetNode(nodeKey);
            if (node?.Type == NodeType.Quest)
                sceneQuestKeys.Add(node.Key);
        }

        foreach (var dbName in _trackerState.TrackedQuests)
        {
            var quest = _graph.GetQuestByDbName(dbName);
            if (quest != null)
                sceneQuestKeys.Add(quest.Key);
        }

        foreach (var dbName in _tracker.GetImplicitlyAvailableQuestDbNames())
        {
            var quest = _graph.GetQuestByDbName(dbName);
            if (quest != null)
                sceneQuestKeys.Add(quest.Key);
        }

        var sw = System.Diagnostics.Stopwatch.StartNew();
        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"Cold marker rebuild: {sceneQuestKeys.Count} quests");
        double totalMs = 0;

        foreach (var questKey in sceneQuestKeys)
        {
            sw.Restart();
            RebuildQuestMarkers(questKey);
            sw.Stop();
            double ms = sw.Elapsed.TotalMilliseconds;
            totalMs += ms;

            var quest = _graph.GetNode(questKey);
            if (ms >= 1.0)
                sb.AppendLine($"  {quest?.DisplayName ?? questKey}: {ms:F1} ms");
        }

        sb.AppendLine($"  total: {totalMs:F0} ms");
        Plugin.Log.LogInfo(sb.ToString());
    }

    private void RebuildQuestMarkers(string questKey)
    {
        RemoveQuestContributions(questKey);

        var quest = _graph.GetNode(questKey);
        if (quest == null || quest.Type != NodeType.Quest || string.IsNullOrEmpty(quest.DbName))
            return;

        bool explicitlySelected = _navSet.Contains(quest.Key)
            || _trackerState.IsTracked(quest.DbName);

        if (explicitlySelected || _tracker.IsActive(quest.DbName))
        {
            var projection = _resolution.GetQuestPlanProjection(quest.Key);
            var targets = _resolution.GetTargetsForScene(quest.Key, _tracker.CurrentZone);
            EmitActiveQuestMarkers(quest, targets);
            return;
        }

        if (_tracker.IsImplicitlyAvailable(quest.DbName))
        {
            EmitImplicitCompletionMarkers(quest);
            return;
        }

        if (!_tracker.IsCompleted(quest.DbName) || quest.Repeatable)
            EmitQuestGiverMarkers(quest);
    }

    private void EmitActiveQuestMarkers(Node quest, IReadOnlyList<ResolvedQuestTarget> targets)
    {
        for (int i = 0; i < targets.Count; i++)
        {
            var target = targets[i];
            var entry = CreateActiveMarkerEntry(quest, target);
            if (entry != null)
                AddContribution(quest.Key, entry.NodeKey, entry);

            var respawnEntry = CreateRespawnTimerEntry(quest, target);
            if (respawnEntry != null)
                AddContribution(quest.Key, respawnEntry.NodeKey, respawnEntry);
        }

        EmitPendingCompletionMarkers(quest, targets);
    }



    private MarkerEntry? CreateRespawnTimerEntry(Node quest, ResolvedQuestTarget target)
    {
        if (target.Semantic.ActionKind != ResolvedActionKind.Kill || !IsCurrentScene(target.Scene))
            return null;

        var positionNode = target.SourceKey != null
            ? _graph.GetNode(target.SourceKey)
            : null;
        if (positionNode == null || positionNode.Type != NodeType.SpawnPoint)
            return null;

        if (!TryGetMarkerPosition(positionNode, out var position))
            return null;

        var info = _liveState.GetSpawnState(positionNode);
        if (info.State is SpawnAlive)
            return null;

        string displayName = target.TargetNode.Node.DisplayName;
        if (info.LiveSpawnPoint != null)
        {
            string timerText = $"{displayName}\n{FormatTimer(info.RespawnSeconds)}";
            return new MarkerEntry
            {
                X = position.x,
                Y = position.y + StaticHeightOffset,
                Z = position.z,
                Scene = positionNode.Scene ?? _tracker.CurrentZone,
                Type = MarkerType.DeadSpawn,
                Priority = 0,
                DisplayName = displayName,
                SubText = timerText,
                NodeKey = positionNode.Key + "|respawn",
                QuestKey = quest.Key,
                LiveSpawnPoint = info.LiveSpawnPoint,
                QuestKind = null,
                QuestPriority = 0,
                QuestSubText = timerText,
                IsSpawnTimer = true,
            };
        }

        if (positionNode.IsDirectlyPlaced)
        {
            string reentryText = $"{displayName}\nRe-enter zone";
            return new MarkerEntry
            {
                X = position.x,
                Y = position.y + StaticHeightOffset,
                Z = position.z,
                Scene = positionNode.Scene ?? _tracker.CurrentZone,
                Type = MarkerType.ZoneReentry,
                Priority = 0,
                DisplayName = displayName,
                SubText = reentryText,
                NodeKey = positionNode.Key + "|respawn",
                QuestKey = quest.Key,
                QuestKind = null,
                QuestPriority = 0,
                QuestSubText = reentryText,
                IsSpawnTimer = true,
            };
        }

        return null;
    }

    private void EmitPendingCompletionMarkers(Node quest, IReadOnlyList<ResolvedQuestTarget> targets)
    {
        bool hasReadyCompletion = targets.Any(target =>
            target.Semantic.PreferredMarkerKind is QuestMarkerKind.TurnInReady or QuestMarkerKind.TurnInRepeatReady);
        if (hasReadyCompletion)
            return;

        var blueprints = _indexes.GetQuestCompletionsInScene(_tracker.CurrentZone);
        for (int i = 0; i < blueprints.Count; i++)
        {
            var blueprint = blueprints[i];
            if (blueprint.QuestKey != quest.Key)
                continue;

            var entry = CreatePendingCompletionEntry(quest, blueprint);
            if (entry != null)
                AddContribution(quest.Key, entry.NodeKey, entry);
        }
    }

    private MarkerEntry? CreatePendingCompletionEntry(Node quest, QuestCompletionBlueprint blueprint)
    {
        var targetNode = _graph.GetNode(blueprint.TargetNodeKey);
        var positionNode = _graph.GetNode(blueprint.PositionNodeKey);
        if (targetNode == null || positionNode == null)
            return null;

        var semantic = ResolvedActionSemanticBuilder.BuildQuestCompletion(
            _graph,
            quest,
            targetNode,
            blueprint,
            ready: false);
        var instruction = MarkerTextBuilder.BuildInstruction(semantic);

        if (targetNode.Type == NodeType.Character)
        {
            return CreateCharacterMarkerEntry(
                quest.Key,
                targetNode.DisplayName,
                instruction.Kind,
                instruction.Priority,
                instruction.SubText,
                targetNode,
                positionNode);
        }

        return CreateStaticMarkerEntry(
            quest.Key,
            positionNode.Key,
            targetNode.DisplayName,
            instruction.Kind,
            instruction.Priority,
            instruction.SubText,
            targetNode,
            positionNode,
            new Vector3(positionNode.X ?? 0f, positionNode.Y ?? 0f, positionNode.Z ?? 0f));
    }

    private void EmitImplicitCompletionMarkers(Node quest)
    {
        // Determine readiness: player holds all required items.
        var requiredEdges = _graph.OutEdges(quest.Key, EdgeType.RequiresItem);
        bool ready = true;
        for (int i = 0; i < requiredEdges.Count; i++)
        {
            int qty = requiredEdges[i].Quantity ?? 1;
            if (_tracker.CountItem(requiredEdges[i].Target) < qty)
            {
                ready = false;
                break;
            }
        }

        // Emit turn-in markers for completion NPCs present in the current scene.
        var blueprints = _indexes.GetQuestCompletionsInScene(_tracker.CurrentZone);
        for (int i = 0; i < blueprints.Count; i++)
        {
            var blueprint = blueprints[i];
            if (blueprint.QuestKey != quest.Key)
                continue;

            var entry = CreateImplicitCompletionEntry(quest, blueprint, ready);
            if (entry != null)
                AddContribution(quest.Key, entry.NodeKey, entry);
        }
    }

    private MarkerEntry? CreateImplicitCompletionEntry(Node quest, QuestCompletionBlueprint blueprint, bool ready)
    {
        var targetNode = _graph.GetNode(blueprint.TargetNodeKey);
        var positionNode = _graph.GetNode(blueprint.PositionNodeKey);
        if (targetNode == null || positionNode == null)
            return null;

        var semantic = ResolvedActionSemanticBuilder.BuildQuestCompletion(
            _graph,
            quest,
            targetNode,
            blueprint,
            ready: ready);
        var instruction = MarkerTextBuilder.BuildInstruction(semantic);

        if (targetNode.Type == NodeType.Character)
        {
            return CreateCharacterMarkerEntry(
                quest.Key,
                targetNode.DisplayName,
                instruction.Kind,
                instruction.Priority,
                instruction.SubText,
                targetNode,
                positionNode);
        }

        return CreateStaticMarkerEntry(
            quest.Key,
            positionNode.Key,
            targetNode.DisplayName,
            instruction.Kind,
            instruction.Priority,
            instruction.SubText,
            targetNode,
            positionNode,
            new Vector3(positionNode.X ?? 0f, positionNode.Y ?? 0f, positionNode.Z ?? 0f));
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

        string? blockedRequirement = FindFirstMissingRequirement(blueprint.RequiredQuestDbNames);
        var semantic = ResolvedActionSemanticBuilder.BuildQuestGiver(
            quest,
            characterNode,
            blueprint,
            blockedRequirement);
        var instruction = MarkerTextBuilder.BuildInstruction(semantic);

        return CreateCharacterMarkerEntry(
            questKey: quest.Key,
            displayName: characterNode.DisplayName,
            questKind: instruction.Kind,
            priority: instruction.Priority,
            subText: instruction.SubText,
            targetNode: characterNode,
            positionNode: positionNode);
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
        if (target.Semantic.ActionKind == ResolvedActionKind.LootChest)
            return CreateLootChestMarkerEntry(quest, target);

        if (!IsCurrentScene(target.Scene))
            return null;

        var targetNode = target.TargetNode.Node;
        var positionNode = target.SourceKey != null
            ? _graph.GetNode(target.SourceKey)
            : targetNode;
        if (positionNode == null)
            return null;

        var instruction = MarkerTextBuilder.BuildInstruction(target.Semantic, target.TargetNode);
        string? corpseSubText = target.Semantic.ActionKind == ResolvedActionKind.Kill
            ? MarkerTextBuilder.BuildCorpseSubText(target.Semantic)
            : null;

        if (targetNode.Type == NodeType.Character)
        {
            return CreateCharacterMarkerEntry(
                quest.Key,
                targetNode.DisplayName,
                instruction.Kind,
                instruction.Priority,
                instruction.SubText,
                targetNode,
                positionNode,
                new Vector3(target.X, target.Y, target.Z),
                target.Semantic.ActionKind == ResolvedActionKind.Kill && target.IsActionable,
                corpseSubText);
        }

        return CreateStaticMarkerEntry(
            quest.Key,
            positionNode.Key,
            targetNode.DisplayName,
            instruction.Kind,
            instruction.Priority,
            instruction.SubText,
            targetNode,
            positionNode,
            new Vector3(target.X, target.Y, target.Z));
    }

    private MarkerEntry? CreateLootChestMarkerEntry(Node quest, ResolvedQuestTarget target)
    {
        if (!IsCurrentScene(target.Scene))
            return null;

        var instruction = MarkerTextBuilder.BuildInstruction(target.Semantic, target.TargetNode);
        var chestPos = new Vector3(target.X, target.Y, target.Z);

        string nodeKey = FormattableString.Invariant(
            $"chest:{target.Scene ?? _tracker.CurrentZone}:{target.X:F2}:{target.Y:F2}:{target.Z:F2}");

        return new MarkerEntry
        {
            X = target.X,
            Y = target.Y + StaticHeightOffset,
            Z = target.Z,
            Scene = target.Scene ?? _tracker.CurrentZone,
            Type = MarkerEntry.ToMarkerType(instruction.Kind),
            Priority = instruction.Priority,
            DisplayName = target.TargetNode.Node.DisplayName,
            SubText = instruction.SubText,
            NodeKey = nodeKey,
            SourceNodeKey = null,
            QuestKey = quest.Key,
            QuestKind = instruction.Kind,
            QuestPriority = instruction.Priority,
            QuestSubText = instruction.SubText,
            IsLootChestTarget = true,
            LiveRotChest = _liveState.GetRotChestNear(chestPos),
        };
    }

    private MarkerEntry? CreateCharacterMarkerEntry(
        string questKey,
        string displayName,
        QuestMarkerKind questKind,
        int priority,
        string subText,
        Node targetNode,
        Node positionNode,
        Vector3? fallbackPosition = null,
        bool keepWhileCorpsePresent = false,
        string? corpseSubText = null)
    {
        SpawnInfo info = positionNode.Type == NodeType.SpawnPoint || positionNode.IsDirectlyPlaced
            ? _liveState.GetSpawnState(positionNode)
            : _liveState.GetCharacterState(targetNode);

        if (info.State is SpawnDisabled)
            return null;

        var (type, resolvedPriority, text) = ResolveCharacterPresentation(
            displayName,
            questKind,
            priority,
            subText,
            info,
            keepWhileCorpsePresent);

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
        // Character markers are keyed by the physical source node. Multiple
        // character nodes can share one spawn; the world marker must collapse
        // to that concrete source rather than duplicate by conceptual identity.
        string contributionNodeKey = positionNode.Key;

        return new MarkerEntry
        {
            X = position.x,
            Y = position.y + StaticHeightOffset,
            Z = position.z,
            Scene = scene,
            Type = type,
            Priority = resolvedPriority,
            DisplayName = displayName,
            SubText = text,
            NodeKey = contributionNodeKey,
            SourceNodeKey = positionNode.Key,
            QuestKey = questKey,
            LiveSpawnPoint = info.LiveSpawnPoint,
            TrackedNPC = info.LiveNPC,
            QuestKind = questKind,
            QuestPriority = priority,
            QuestSubText = subText,
            KeepWhileCorpsePresent = keepWhileCorpsePresent,
            CorpseSubText = corpseSubText,
        };
    }


    private static bool IsCorpsePresent(SpawnInfo info) =>
        info.State is SpawnDead
        && info.LiveNPC != null
        && info.LiveNPC.gameObject != null;

    private static (MarkerType Type, int Priority, string SubText) ResolveCharacterPresentation(
        string displayName,
        QuestMarkerKind questKind,
        int priority,
        string subText,
        SpawnInfo info,
        bool keepWhileCorpsePresent)
    {
        if (keepWhileCorpsePresent && IsCorpsePresent(info))
            return (MarkerEntry.ToMarkerType(questKind), priority, subText);

        return info.State switch
        {
            SpawnAlive => (MarkerEntry.ToMarkerType(questKind), priority, subText),
            SpawnDead dead => (MarkerType.DeadSpawn, 0, $"{displayName}\n{FormatTimer(dead.RespawnSeconds)}"),
            SpawnNightLocked => (MarkerType.NightSpawn, 0, BuildNightLockedText(displayName)),
            SpawnUnlockBlocked blocked => (MarkerType.QuestLocked, 0, $"{displayName}\n{blocked.Reason}"),
            SpawnDisabled => (MarkerEntry.ToMarkerType(questKind), priority, subText),
            _ => (MarkerEntry.ToMarkerType(questKind), priority, subText),
        };
    }

    private MarkerEntry? CreateStaticMarkerEntry(
        string questKey,
        string nodeKey,
        string displayName,
        QuestMarkerKind questKind,
        int priority,
        string subText,
        Node targetNode,
        Node positionNode,
        Vector3 fallbackPosition)
    {
        var type = MarkerEntry.ToMarkerType(questKind);
        int resolvedPriority = priority;
        var text = subText;
        MiningNode? liveMining = null;

        if (targetNode.Type == NodeType.MiningNode)
        {
            var mining = _liveState.GetMiningState(targetNode);
            liveMining = mining.LiveNode;
            if (mining.State is MiningMined mined)
            {
                type = MarkerType.DeadSpawn;
                resolvedPriority = 0;
                text = $"{displayName}\n{FormatTimer(mined.RespawnSeconds)}";
            }
        }
        else if (targetNode.Type == NodeType.ItemBag)
        {
            var bagState = _liveState.GetItemBagState(targetNode);
            if (bagState is ItemBagPickedUp)
            {
                type = MarkerType.ZoneReentry;
                resolvedPriority = 0;
                text = $"{displayName}\nRe-enter zone";
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
            Priority = resolvedPriority,
            DisplayName = displayName,
            SubText = text,
            NodeKey = nodeKey,
            SourceNodeKey = positionNode.Key,
            QuestKey = questKey,
            LiveMiningNode = liveMining,
            QuestKind = questKind,
            QuestPriority = priority,
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

        if (!byQuest.TryGetValue(questKey, out var existing)
            || entry.Priority < existing.Priority
            || (entry.Priority == existing.Priority && entry.Type < existing.Type))
        {
            byQuest[questKey] = entry;
        }

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
                if (best == null
                    || entry.Priority < best.Priority
                    || (entry.Priority == best.Priority && entry.Type < best.Type))
                {
                    best = entry;
                }
            }

            if (best != null)
                _markers.Add(CloneEntry(best));
        }

        SuppressBlockedMarkersAtOccupiedPositions();

        Version++;
    }

    /// <summary>
    /// Removes QuestGiverBlocked and QuestLocked markers whose spawn point is
    /// already occupied by a non-blocked marker. Spawn point positions from the
    /// graph are used for comparison — not the rendered marker coordinates, which
    /// may differ between static and live-NPC paths. Exact float equality is
    /// correct: co-located NPCs share the same exported spawn node coordinates.
    /// A blocked variant at the same spot adds no value when the player can
    /// already act there, and suppression must be stable even if an NPC has moved.
    /// </summary>
    private void SuppressBlockedMarkersAtOccupiedPositions()
    {
        static bool IsBlocked(MarkerType t) =>
            t is MarkerType.QuestGiverBlocked or MarkerType.QuestLocked;

        // First pass: collect spawn-point positions that have a non-blocked marker.
        var occupiedByNonBlocked = new HashSet<(float X, float Y, float Z)>();
        for (int i = 0; i < _markers.Count; i++)
        {
            if (IsBlocked(_markers[i].Type)) continue;
            var sourceKey = _markers[i].SourceNodeKey;
            if (sourceKey == null) continue;
            var node = _graph.GetNode(sourceKey);
            if (node?.X == null || node.Y == null || node.Z == null) continue;
            occupiedByNonBlocked.Add((node.X.Value, node.Y.Value, node.Z.Value));
        }

        if (occupiedByNonBlocked.Count == 0)
            return;

        // Second pass: remove blocked entries whose spawn point is in that set.
        int write = 0;
        for (int read = 0; read < _markers.Count; read++)
        {
            var m = _markers[read];
            if (IsBlocked(m.Type) && m.SourceNodeKey != null)
            {
                var node = _graph.GetNode(m.SourceNodeKey);
                if (node?.X != null && node.Y != null && node.Z != null
                    && occupiedByNonBlocked.Contains((node.X.Value, node.Y.Value, node.Z.Value)))
                {
                    continue;
                }
            }
            _markers[write++] = m;
        }
        _markers.RemoveRange(write, _markers.Count - write);
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

    private static MarkerEntry CloneEntry(MarkerEntry entry) => new()
    {
        X = entry.X,
        Y = entry.Y,
        Z = entry.Z,
        Scene = entry.Scene,
        Type = entry.Type,
        Priority = entry.Priority,
        DisplayName = entry.DisplayName,
        SubText = entry.SubText,
        NodeKey = entry.NodeKey,
        SourceNodeKey = entry.SourceNodeKey,
        QuestKey = entry.QuestKey,
        LiveSpawnPoint = entry.LiveSpawnPoint,
        TrackedNPC = entry.TrackedNPC,
        LiveMiningNode = entry.LiveMiningNode,
        QuestKind = entry.QuestKind,
        QuestPriority = entry.QuestPriority,
        QuestSubText = entry.QuestSubText,
        KeepWhileCorpsePresent = entry.KeepWhileCorpsePresent,
        CorpseSubText = entry.CorpseSubText,
        IsSpawnTimer = entry.IsSpawnTimer,
        LiveRotChest = entry.LiveRotChest,
        IsLootChestTarget = entry.IsLootChestTarget,
    };

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
