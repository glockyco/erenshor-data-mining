using System.Diagnostics;
using AdventureGuide.Diagnostics;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using UnityEngine;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Markers;

/// <summary>
/// Scene-local world marker projection.
/// Quest semantics come from compiled frontier/source resolvers and immutable
/// graph blueprints; this class only materializes markers for the current scene.
/// </summary>
public sealed class MarkerComputer
{
    private const float StaticHeightOffset = 2.5f;
    private const int MaxRecentDiagnosticSamples = 8;

    private readonly QuestStateTracker _tracker;
    private readonly LiveStateTracker _liveState;
    private readonly NavigationSet _navSet;
    private readonly TrackerState _trackerState;
    private readonly MarkerQuestTargetResolver _questTargetResolver;
    private readonly CompiledGuideModel _compiledGuide;
    private readonly DiagnosticsCore? _diagnostics;

    private readonly List<MarkerEntry> _markers = new();
    private readonly Dictionary<string, Dictionary<string, MarkerEntry>> _contributionsByNode = new(
        StringComparer.Ordinal
    );
    private readonly Dictionary<string, HashSet<string>> _nodesByQuest = new(
        StringComparer.Ordinal
    );
    private readonly HashSet<string> _pendingQuestKeys = new(StringComparer.Ordinal);
    private readonly List<QuestCostSample> _recentQuestCosts = new();
    private readonly List<MarkerRebuildModeSample> _recentModes = new();

    private bool _dirty = true;
    private bool _fullRebuild = true;
    private DiagnosticTrigger _lastDiagnosticTrigger = DiagnosticTrigger.Unknown;
    private long _lastRecomputeTicks;

    public IReadOnlyList<MarkerEntry> Markers => _markers;
    public int Version { get; private set; }

    internal MarkerComputer(
        CompiledGuideModel compiledGuide,
        QuestStateTracker tracker,
        LiveStateTracker liveState,
        NavigationSet navSet,
        TrackerState trackerState,
        MarkerQuestTargetResolver questTargetResolver,
        DiagnosticsCore? diagnostics = null
    )
    {
        _compiledGuide = compiledGuide;
        _tracker = tracker;
        _liveState = liveState;
        _navSet = navSet;
        _trackerState = trackerState;
        _questTargetResolver = questTargetResolver;
        _diagnostics = diagnostics;

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

    private void OnExternalSelectionChanged() => MarkDirty(DiagnosticTrigger.NavSetChanged);

    private void OnTrackedChanged(string _) => MarkDirty(DiagnosticTrigger.TrackedQuestSetChanged);

    public void ApplyGuideChangeSet(GuideChangeSet changeSet)
    {
        var trigger = ResolveTrigger(changeSet);
        var context = DiagnosticsContext.Root(trigger);
        var token = _diagnostics?.BeginSpan(
            DiagnosticSpanKind.MarkerApplyGuideChangeSet,
            context,
            primaryKey: "MarkerComputer"
        );
        long startTick = Stopwatch.GetTimestamp();
        try
        {
            var plan = MaintainedViewPlanner.Plan(
                CollectActiveQuestKeysForPlanning(),
                changeSet,
                liveWorldChanged: changeSet.LiveWorldChanged,
                targetSourceVersionChanged: false,
                navSetVersionChanged: false
            );
            if (!plan.RequiresRefresh)
                return;

            _dirty = true;
            _lastDiagnosticTrigger = plan.Reason;
            _diagnostics?.RecordEvent(
                new DiagnosticEvent(
                    DiagnosticEventKind.MarkerRebuildRequested,
                    context,
                    timestampTicks: startTick,
                    primaryKey: "MarkerComputer",
                    value0: plan.IsFullRebuild ? 1 : 0,
                    value1: plan.Keys.Count
                )
            );

            if (plan.IsFullRebuild)
            {
                _fullRebuild = true;
                _pendingQuestKeys.Clear();
                return;
            }

            foreach (var questKey in plan.Keys)
                _pendingQuestKeys.Add(questKey);
        }
        finally
        {
            if (token != null)
                _diagnostics!.EndSpan(
                    token.Value,
                    Stopwatch.GetTimestamp() - startTick,
                    value0: _fullRebuild ? 1 : 0,
                    value1: _pendingQuestKeys.Count
                );
        }
    }

    /// <summary>
    /// Fallback for live-world updates that do not currently produce structured
    /// quest deltas. Used by spawn/mining/item-bag patches.
    /// </summary>
    public void MarkDirty()
    {
        MarkDirty(DiagnosticTrigger.LiveWorldChanged);
    }

    private void MarkDirty(DiagnosticTrigger trigger)
    {
        _dirty = true;
        _fullRebuild = true;
        _lastDiagnosticTrigger = trigger;
        _diagnostics?.RecordEvent(
            new DiagnosticEvent(
                DiagnosticEventKind.MarkerRebuildRequested,
                DiagnosticsContext.Root(trigger),
                timestampTicks: Stopwatch.GetTimestamp(),
                primaryKey: "MarkerComputer",
                value0: 1,
                value1: _pendingQuestKeys.Count
            )
        );
    }

    public void Recompute()
    {
        if (!_dirty)
            return;

        var mode = _fullRebuild ? MarkerRebuildMode.Full : MarkerRebuildMode.Incremental;
        var context = DiagnosticsContext.Root(_lastDiagnosticTrigger);
        var token = _diagnostics?.BeginSpan(
            DiagnosticSpanKind.MarkerRecompute,
            context,
            primaryKey: "MarkerComputer"
        );
        long startTick = Stopwatch.GetTimestamp();
        try
        {
            _dirty = false;

            if (string.IsNullOrEmpty(_tracker.CurrentZone))
            {
                ClearAll();
                PublishMarkersWithDiagnostics(context);
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
                var resolutionSession = new SourceResolver.ResolutionSession();
                foreach (var questKey in _pendingQuestKeys)
                    RebuildQuestMarkers(questKey, resolutionSession, compiledTargetsByQuestKey: null);

                _pendingQuestKeys.Clear();
            }

            PublishMarkersWithDiagnostics(context);
        }
        finally
        {
            _lastRecomputeTicks = Stopwatch.GetTimestamp() - startTick;
            AddRecentMode(mode);
            if (token != null)
                _diagnostics!.EndSpan(
                    token.Value,
                    _lastRecomputeTicks,
                    value0: mode == MarkerRebuildMode.Full ? 1 : 0,
                    value1: _markers.Count
                );
        }
    }

    private HashSet<string> CollectActiveQuestKeysForPlanning()
    {
        var questKeys = new HashSet<string>(StringComparer.Ordinal);
        foreach (var blueprint in GetQuestGiversInCurrentScene())
            questKeys.Add(blueprint.QuestKey);

        foreach (var questDbName in _tracker.GetActionableQuestDbNames())
        {
            var quest = _compiledGuide.GetQuestByDbName(questDbName);
            if (quest != null)
                questKeys.Add(quest.Key);
        }

        foreach (var nodeKey in _navSet.Keys)
        {
            var node = _compiledGuide.GetNode(nodeKey);
            if (node?.Type == NodeType.Quest)
                questKeys.Add(node.Key);
        }

        foreach (var dbName in _trackerState.TrackedQuests)
        {
            var quest = _compiledGuide.GetQuestByDbName(dbName);
            if (quest != null)
                questKeys.Add(quest.Key);
        }

        foreach (var dbName in _tracker.GetImplicitlyAvailableQuestDbNames())
        {
            var quest = _compiledGuide.GetQuestByDbName(dbName);
            if (quest != null)
                questKeys.Add(quest.Key);
        }

        return questKeys;
    }

    private void RebuildCurrentScene()
    {
        var token = _diagnostics?.BeginSpan(
            DiagnosticSpanKind.MarkerRebuildCurrentScene,
            DiagnosticsContext.Root(_lastDiagnosticTrigger),
            primaryKey: _tracker.CurrentZone
        );
        long startTick = Stopwatch.GetTimestamp();
        try
        {
            ClearAll();

            var collectionToken = _diagnostics?.BeginSpan(
                DiagnosticSpanKind.MarkerCollectSceneQuestKeys,
                DiagnosticsContext.Root(_lastDiagnosticTrigger),
                primaryKey: _tracker.CurrentZone
            );
            long collectionStart = Stopwatch.GetTimestamp();
            var sceneQuestKeys = CollectActiveQuestKeysForPlanning();

            if (collectionToken != null)
                _diagnostics!.EndSpan(
                    collectionToken.Value,
                    Stopwatch.GetTimestamp() - collectionStart,
                    value0: sceneQuestKeys.Count,
                    value1: 0
                );

            var resolutionSession = new SourceResolver.ResolutionSession();
            var batchToken = _diagnostics?.BeginSpan(
                DiagnosticSpanKind.MarkerBatchResolveQuests,
                DiagnosticsContext.Root(_lastDiagnosticTrigger),
                primaryKey: _tracker.CurrentZone
            );
            long batchStart = Stopwatch.GetTimestamp();
            var compiledTargetsByQuestKey = _questTargetResolver.ResolveQuestKeys(
                sceneQuestKeys,
                _tracker.CurrentZone,
                resolutionSession
            );
            if (batchToken != null)
                _diagnostics!.EndSpan(
                    batchToken.Value,
                    Stopwatch.GetTimestamp() - batchStart,
                    value0: sceneQuestKeys.Count,
                    value1: compiledTargetsByQuestKey.Count
                );
            var sw = Stopwatch.StartNew();
            _recentQuestCosts.Clear();
            var rebuildToken = _diagnostics?.BeginSpan(
                DiagnosticSpanKind.MarkerRebuildSceneQuestTargets,
                DiagnosticsContext.Root(_lastDiagnosticTrigger),
                primaryKey: _tracker.CurrentZone
            );
            long rebuildStart = Stopwatch.GetTimestamp();
            foreach (var questKey in sceneQuestKeys)
            {
                sw.Restart();
                RebuildQuestMarkers(questKey, resolutionSession, compiledTargetsByQuestKey);
                sw.Stop();
                AddQuestCostSample(questKey, sw.ElapsedTicks);
            }

            if (rebuildToken != null)
                _diagnostics!.EndSpan(
                    rebuildToken.Value,
                    Stopwatch.GetTimestamp() - rebuildStart,
                    value0: sceneQuestKeys.Count,
                    value1: 0
                );
        }
        finally
        {
            if (token != null)
                _diagnostics!.EndSpan(
                    token.Value,
                    Stopwatch.GetTimestamp() - startTick,
                    value0: _recentQuestCosts.Count,
                    value1: _markers.Count
                );
        }
    }

    private void RebuildQuestMarkers(
        string questKey,
        SourceResolver.ResolutionSession resolutionSession,
        IReadOnlyDictionary<string, IReadOnlyList<ResolvedTarget>>? compiledTargetsByQuestKey
    )
    {
        var token = _diagnostics?.BeginSpan(
            DiagnosticSpanKind.MarkerRebuildQuest,
            DiagnosticsContext.Root(_lastDiagnosticTrigger),
            primaryKey: questKey
        );
        long startTick = Stopwatch.GetTimestamp();
        try
        {
            RemoveQuestContributions(questKey);

            var quest = _compiledGuide.GetNode(questKey);
            if (quest == null || quest.Type != NodeType.Quest || string.IsNullOrEmpty(quest.DbName))
                return;

            bool explicitlySelected =
                _navSet.Contains(quest.Key) || _trackerState.IsTracked(quest.DbName);

            if (explicitlySelected || _tracker.IsActive(quest.DbName))
            {
                IReadOnlyList<ResolvedTarget> compiledTargets;
                if (
                    compiledTargetsByQuestKey != null
                    && compiledTargetsByQuestKey.TryGetValue(quest.Key, out var precomputedTargets)
                )
                    compiledTargets = precomputedTargets;
                else
                    compiledTargets = _questTargetResolver.Resolve(
                        quest.DbName,
                        _tracker.CurrentZone,
                        resolutionSession
                    );
                EmitActiveQuestMarkers(quest, compiledTargets);
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
        finally
        {
            if (token != null)
                _diagnostics!.EndSpan(token.Value, Stopwatch.GetTimestamp() - startTick);
        }
    }

    private void EmitActiveQuestMarkers(Node quest, IReadOnlyList<ResolvedTarget> targets)
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
    }

    private MarkerEntry? CreateRespawnTimerEntry(Node quest, ResolvedTarget target)
    {
        if (!IsCurrentScene(target.Scene))
            return null;

        var positionNode = _compiledGuide.GetNode(_compiledGuide.GetNodeKey(target.PositionNodeId));
        if (positionNode == null || positionNode.Type != NodeType.SpawnPoint)
            return null;

        if (!TryGetMarkerPosition(positionNode, out var position))
            return null;

        var info = _liveState.GetSpawnState(positionNode);
        if (info.State is SpawnAlive)
            return null;

        // Respawn timers are only meaningful for SpawnDead (with a real timer)
        // and SpawnNightLocked (time-based gate). SpawnDisabled has no respawn
        // path; SpawnUnlockBlocked already shows a QuestLocked marker from the
        // character marker path.
        if (info.State is SpawnDisabled or SpawnUnlockBlocked)
            return null;

        string displayName =
            _compiledGuide.GetNode(_compiledGuide.GetNodeKey(target.TargetNodeId))?.DisplayName
            ?? _compiledGuide.GetDisplayName(target.TargetNodeId);

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

    private MarkerEntry? CreatePendingCompletionEntry(
        Node quest,
        QuestCompletionBlueprint blueprint
    )
    {
        var targetNode = _compiledGuide.GetNode(blueprint.TargetNodeKey);
        var positionNode = _compiledGuide.GetNode(blueprint.PositionNodeKey);
        if (targetNode == null || positionNode == null)
            return null;

        var semantic = ResolvedActionSemanticBuilder.BuildQuestCompletion(
            _compiledGuide,
            quest,
            targetNode,
            blueprint,
            ready: false
        );
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
                positionNode
            );
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
            new Vector3(positionNode.X ?? 0f, positionNode.Y ?? 0f, positionNode.Z ?? 0f)
        );
    }

    private void EmitImplicitCompletionMarkers(Node quest)
    {
        // Determine readiness: player holds all required items.
        var requiredEdges = _compiledGuide.OutEdges(quest.Key, EdgeType.RequiresItem);
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
        foreach (var blueprint in GetQuestCompletionsInCurrentScene())
        {
            if (blueprint.QuestKey != quest.Key)
                continue;

            var entry = CreateImplicitCompletionEntry(quest, blueprint, ready);
            if (entry != null)
                AddContribution(quest.Key, entry.NodeKey, entry);
        }
    }

    private MarkerEntry? CreateImplicitCompletionEntry(
        Node quest,
        QuestCompletionBlueprint blueprint,
        bool ready
    )
    {
        var targetNode = _compiledGuide.GetNode(blueprint.TargetNodeKey);
        var positionNode = _compiledGuide.GetNode(blueprint.PositionNodeKey);
        if (targetNode == null || positionNode == null)
            return null;

        var semantic = ResolvedActionSemanticBuilder.BuildQuestCompletion(
            _compiledGuide,
            quest,
            targetNode,
            blueprint,
            ready: ready
        );
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
                positionNode
            );
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
            new Vector3(positionNode.X ?? 0f, positionNode.Y ?? 0f, positionNode.Z ?? 0f)
        );
    }

    private MarkerEntry? CreateActiveMarkerEntry(Node quest, ResolvedTarget target)
    {
        if (!IsCurrentScene(target.Scene))
            return null;

        var targetNode = _compiledGuide.GetNode(_compiledGuide.GetNodeKey(target.TargetNodeId));
        var positionNode = _compiledGuide.GetNode(_compiledGuide.GetNodeKey(target.PositionNodeId));
        if (targetNode == null || positionNode == null)
            return null;

        var instruction = MarkerTextBuilder.BuildInstruction(target.Semantic);
        string? corpseSubText =
            target.Semantic.ActionKind == ResolvedActionKind.Kill
                ? MarkerTextBuilder.BuildCorpseSubText(target.Semantic)
                : null;

        if (targetNode.Type == NodeType.Character)
        {
            if (!CharacterMarkerPolicy.ShouldEmitActiveMarker(target))
                return null;

            return CreateCharacterMarkerEntry(
                quest.Key,
                targetNode.DisplayName,
                instruction.Kind,
                instruction.Priority,
                instruction.SubText,
                targetNode,
                positionNode,
                new Vector3(target.X, target.Y, target.Z),
                CharacterMarkerPolicy.ShouldKeepQuestMarkerOnCorpse(target),
                corpseSubText
            );
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
            new Vector3(target.X, target.Y, target.Z)
        );
    }

    private void EmitQuestGiverMarkers(Node quest)
    {
        foreach (var blueprint in GetQuestGiversInCurrentScene())
        {
            if (blueprint.QuestKey != quest.Key)
                continue;

            var entry = CreateQuestGiverEntry(quest, blueprint);
            if (entry != null)
                AddContribution(quest.Key, entry.NodeKey, entry);
        }
    }

    private IReadOnlyList<QuestGiverBlueprint> GetQuestGiversInCurrentScene() =>
        _compiledGuide.GetQuestGiversInScene(_tracker.CurrentZone);

    private IReadOnlyList<QuestCompletionBlueprint> GetQuestCompletionsInCurrentScene() =>
        _compiledGuide.GetQuestCompletionsInScene(_tracker.CurrentZone);

    private MarkerEntry? CreateQuestGiverEntry(Node quest, QuestGiverBlueprint blueprint)
    {
        var characterNode = _compiledGuide.GetNode(blueprint.CharacterKey);
        var positionNode = _compiledGuide.GetNode(blueprint.PositionNodeKey);
        if (characterNode == null || positionNode == null)
            return null;

        string? blockedRequirement = FindFirstMissingRequirement(blueprint.RequiredQuestDbNames);
        var semantic = ResolvedActionSemanticBuilder.BuildQuestGiver(
            _compiledGuide,
            quest,
            characterNode,
            blueprint,
            blockedRequirement
        );
        var instruction = MarkerTextBuilder.BuildInstruction(semantic);

        return CreateCharacterMarkerEntry(
            questKey: quest.Key,
            displayName: characterNode.DisplayName,
            questKind: instruction.Kind,
            priority: instruction.Priority,
            subText: instruction.SubText,
            targetNode: characterNode,
            positionNode: positionNode
        );
    }

    private string? FindFirstMissingRequirement(IReadOnlyList<string> requiredQuestDbNames)
    {
        for (int i = 0; i < requiredQuestDbNames.Count; i++)
        {
            var dbName = requiredQuestDbNames[i];
            if (_tracker.IsCompleted(dbName))
                continue;

            var quest = _compiledGuide.GetQuestByDbName(dbName);
            return quest?.DisplayName ?? dbName;
        }

        return null;
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
        string? corpseSubText = null
    )
    {
        SpawnInfo info =
            positionNode.Type == NodeType.SpawnPoint || positionNode.IsDirectlyPlaced
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
            keepWhileCorpsePresent
        );

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

        string scene = positionNode.Scene ?? targetNode.Scene ?? _tracker.CurrentZone;
        string contributionNodeKey = TargetInstanceIdentity.Get(targetNode.Key, positionNode.Key);

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
        info.State is SpawnDead && info.LiveNPC != null && info.LiveNPC.gameObject != null;

    private static (MarkerType Type, int Priority, string SubText) ResolveCharacterPresentation(
        string displayName,
        QuestMarkerKind questKind,
        int priority,
        string subText,
        SpawnInfo info,
        bool keepWhileCorpsePresent
    )
    {
        if (keepWhileCorpsePresent && IsCorpsePresent(info))
            return (MarkerEntry.ToMarkerType(questKind), priority, subText);

        return info.State switch
        {
            SpawnAlive => (MarkerEntry.ToMarkerType(questKind), priority, subText),
            SpawnDead dead => (
                MarkerType.DeadSpawn,
                0,
                $"{displayName}\n{FormatTimer(dead.RespawnSeconds)}"
            ),
            SpawnNightLocked => (MarkerType.NightSpawn, 0, BuildNightLockedText(displayName)),
            SpawnUnlockBlocked blocked => (
                MarkerType.QuestLocked,
                0,
                $"{displayName}\n{blocked.Reason}"
            ),
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
        Vector3 fallbackPosition
    )
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

        if (
            !byQuest.TryGetValue(questKey, out var existing)
            || entry.Priority < existing.Priority
            || (entry.Priority == existing.Priority && entry.Type < existing.Type)
        )
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

    private int PublishMarkers()
    {
        _markers.Clear();
        foreach (var byQuest in _contributionsByNode.Values)
        {
            MarkerEntry? best = null;
            foreach (var entry in byQuest.Values)
            {
                if (
                    best == null
                    || entry.Priority < best.Priority
                    || (entry.Priority == best.Priority && entry.Type < best.Type)
                )
                {
                    best = entry;
                }
            }

            if (best != null)
                _markers.Add(CloneEntry(best));
        }

        int suppressedMarkers = SuppressBlockedMarkersAtOccupiedPositions();

        Version++;
        return suppressedMarkers;
    }

    private int SuppressBlockedMarkersAtOccupiedPositions()
    {
        static bool IsBlocked(MarkerType t) =>
            t is MarkerType.QuestGiverBlocked or MarkerType.QuestLocked;

        // First pass: collect spawn-point positions that have a non-blocked marker.
        var occupiedByNonBlocked = new HashSet<(float X, float Y, float Z)>();
        for (int i = 0; i < _markers.Count; i++)
        {
            if (IsBlocked(_markers[i].Type))
                continue;
            var sourceKey = _markers[i].SourceNodeKey;
            if (sourceKey == null)
                continue;
            var node = _compiledGuide.GetNode(sourceKey);
            if (node?.X == null || node.Y == null || node.Z == null)
                continue;
            occupiedByNonBlocked.Add((node.X.Value, node.Y.Value, node.Z.Value));
        }

        if (occupiedByNonBlocked.Count == 0)
            return 0;

        // Second pass: remove blocked entries whose spawn point is in that set.
        int write = 0;
        int suppressed = 0;
        for (int read = 0; read < _markers.Count; read++)
        {
            var m = _markers[read];
            if (IsBlocked(m.Type) && m.SourceNodeKey != null)
            {
                var node = _compiledGuide.GetNode(m.SourceNodeKey);
                if (
                    node?.X != null
                    && node.Y != null
                    && node.Z != null
                    && occupiedByNonBlocked.Contains((node.X.Value, node.Y.Value, node.Z.Value))
                )
                {
                    suppressed++;
                    continue;
                }
            }
            _markers[write++] = m;
        }
        _markers.RemoveRange(write, _markers.Count - write);
        return suppressed;
    }

    private void PublishMarkersWithDiagnostics(DiagnosticsContext context)
{
    var token = _diagnostics?.BeginSpan(
        DiagnosticSpanKind.MarkerPublishMarkers,
        context,
        primaryKey: _tracker.CurrentZone
    );
    long startTick = Stopwatch.GetTimestamp();
    int suppressedMarkers = PublishMarkers();
    if (token != null)
        _diagnostics!.EndSpan(
            token.Value,
            Stopwatch.GetTimestamp() - startTick,
            value0: _markers.Count,
            value1: suppressedMarkers
        );
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

    private static MarkerEntry CloneEntry(MarkerEntry entry) =>
        new()
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

    private static DiagnosticTrigger ResolveTrigger(GuideChangeSet changeSet)
    {
        if (changeSet.SceneChanged)
            return DiagnosticTrigger.SceneChanged;
        if (changeSet.LiveWorldChanged)
            return DiagnosticTrigger.LiveWorldChanged;
        if (changeSet.InventoryChanged)
            return DiagnosticTrigger.InventoryChanged;
        if (changeSet.QuestLogChanged)
            return DiagnosticTrigger.QuestLogChanged;
        return DiagnosticTrigger.Unknown;
    }

    private void AddQuestCostSample(string questKey, long elapsedTicks)
    {
        _recentQuestCosts.Add(new QuestCostSample(questKey, elapsedTicks));
        _recentQuestCosts.Sort((left, right) => right.ElapsedTicks.CompareTo(left.ElapsedTicks));
        if (_recentQuestCosts.Count > MaxRecentDiagnosticSamples)
            _recentQuestCosts.RemoveRange(
                MaxRecentDiagnosticSamples,
                _recentQuestCosts.Count - MaxRecentDiagnosticSamples
            );
    }

    private void AddRecentMode(MarkerRebuildMode mode)
    {
        _recentModes.Add(new MarkerRebuildModeSample(mode, Stopwatch.GetTimestamp()));
        if (_recentModes.Count > MaxRecentDiagnosticSamples)
            _recentModes.RemoveRange(0, _recentModes.Count - MaxRecentDiagnosticSamples);
    }

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

    internal MarkerDiagnosticsSnapshot ExportDiagnosticsSnapshot()
    {
        return new MarkerDiagnosticsSnapshot(
            fullRebuild: _fullRebuild,
            pendingQuestCount: _pendingQuestKeys.Count,
            lastReason: _lastDiagnosticTrigger,
            lastDurationTicks: _lastRecomputeTicks,
            topQuestCosts: _recentQuestCosts.ToArray(),
            recentModes: _recentModes.ToArray()
        );
    }

    internal IReadOnlyCollection<string>? GetContributingQuestKeys(string nodeKey)
    {
        if (_contributionsByNode.TryGetValue(nodeKey, out var byQuest))
            return byQuest.Keys;
        return null;
    }
}
