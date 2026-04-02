using AdventureGuide.Plan;
using AdventureGuide.Graph;
using AdventureGuide.Navigation;
using AdventureGuide.Position;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.Resolution;

/// <summary>
/// Canonical quest semantics layer.
/// Separates expensive structural quest builds from source-sensitive target
/// resolution so live-world source changes can invalidate only the cheap layer.
/// </summary>
public sealed class QuestResolutionService
{
    private readonly EntityGraph _graph;
    private readonly QuestStateTracker _tracker;
    private readonly GameState _gameState;
    private readonly QuestPlanBuilder _planBuilder;
    private readonly GuideDependencyEngine _dependencies;
    private readonly CompiledSourceIndex _sourceIndex;
    private readonly SourcePositionCache _positionCache;
    private readonly UnlockEvaluator _unlocks;
    private readonly ZoneRouter _router;
    private readonly ZoneAccessResolver _zoneAccess;

    private readonly Dictionary<string, QuestPlan> _planCache = new(StringComparer.Ordinal);
    private readonly Dictionary<string, QuestPlanProjection> _planProjectionCache = new(StringComparer.Ordinal);
    private readonly Dictionary<string, IReadOnlyList<ResolvedQuestTarget>> _targetCache = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Dictionary<string, IReadOnlyList<ResolvedQuestTarget>>> _sceneTargetCache = new(StringComparer.Ordinal);
    private readonly Dictionary<string, QuestResolution> _resolutionCache = new(StringComparer.Ordinal);

    public int Version { get; private set; }

    public QuestResolutionService(
        EntityGraph graph,
        QuestStateTracker tracker,
        GameState gameState,
        QuestPlanBuilder planBuilder,
        GuideDependencyEngine dependencies,
        CompiledSourceIndex sourceIndex,
        SourcePositionCache positionCache,
        UnlockEvaluator unlocks,
        ZoneRouter router)
    {
        _graph = graph;
        _tracker = tracker;
        _gameState = gameState;
        _planBuilder = planBuilder;
        _dependencies = dependencies;
        _sourceIndex = sourceIndex;
        _positionCache = positionCache;
        _unlocks = unlocks;
        _router = router;
        _zoneAccess = new ZoneAccessResolver(graph, tracker, unlocks, router);
    }

    public GuideChangeSet ApplyChangeSet(GuideChangeSet changeSet)
    {
        if (changeSet == null || !changeSet.HasMeaningfulChanges)
            return GuideChangeSet.None;

        if (changeSet.SceneChanged)
        {
            if (_planCache.Count > 0 || _planProjectionCache.Count > 0 || _targetCache.Count > 0 || _sceneTargetCache.Count > 0 || _resolutionCache.Count > 0)
            {
                _planCache.Clear();
                _planProjectionCache.Clear();
                _targetCache.Clear();
                _sceneTargetCache.Clear();
                _resolutionCache.Clear();
                _dependencies.Clear();
                _positionCache.Clear();
                Version++;
            }

            return changeSet;
        }

        var targetInvalidations = new HashSet<string>(changeSet.AffectedQuestKeys, StringComparer.Ordinal);
        bool planChange = changeSet.InventoryChanged || changeSet.QuestLogChanged || changeSet.LiveWorldChanged;

        foreach (var derivedKey in _dependencies.InvalidateFacts(changeSet.ChangedFacts))
        {
            switch (derivedKey.Kind)
            {
                case GuideDerivedKind.QuestTargets:
                    targetInvalidations.Add(derivedKey.Key);
                    break;
            }
        }

        if (planChange)
            targetInvalidations.UnionWith(changeSet.AffectedQuestKeys);

        bool removedAny = false;
        foreach (var questKey in targetInvalidations)
        {
            removedAny |= _planCache.Remove(questKey);
            removedAny |= _planProjectionCache.Remove(questKey);
            removedAny |= _targetCache.Remove(questKey);
            removedAny |= _sceneTargetCache.Remove(questKey);
            removedAny |= _resolutionCache.Remove(questKey);
        }


        // Evict cached source positions for changed live-world sources.
        // This ensures the next resolution sees fresh NPC positions.
        if (changeSet.LiveWorldChanged)
        {
            foreach (var fact in changeSet.ChangedFacts)
            {
                if (fact.Kind == GuideFactKind.SourceState)
                    _positionCache.Invalidate(fact.Key);
            }
        }
        if (removedAny)
            Version++;

        return targetInvalidations.SetEquals(changeSet.AffectedQuestKeys)
            ? changeSet
            : changeSet.WithAffectedQuestKeys(targetInvalidations);
    }

    public QuestResolution? GetQuestResolutionByDbName(string dbName)
    {
        var quest = _graph.GetQuestByDbName(dbName);
        return quest == null ? null : ResolveQuest(quest.Key);
    }

    public QuestResolution ResolveQuest(string questKey)
    {
        if (_resolutionCache.TryGetValue(questKey, out var cached))
            return cached;

        var projection = GetQuestPlanProjection(questKey);
        var questNode = _graph.GetNode(questKey);
        var targets = ResolveTargets(questKey, projection, questNode);
        var trackerSummary = BuildTrackerSummary(questNode, questKey, projection, targets);

        var resolution = new QuestResolution(
            questKey,
            projection,
            targets,
            trackerSummary);
        _resolutionCache[questKey] = resolution;
        return resolution;
    }

    /// <summary>Returns the cached canonical plan, building it on first access.</summary>
    public QuestPlan GetQuestPlan(string questKey)
    {
        if (_planCache.TryGetValue(questKey, out var cached))
            return cached;

        var plan = _planBuilder.Build(questKey);
        _planCache[questKey] = plan;
        return plan;
    }

    /// <summary>Returns the canonical plan plus shared frontier/tracker/nav projections.</summary>
    public QuestPlanProjection GetQuestPlanProjection(string questKey)
    {
        if (_planProjectionCache.TryGetValue(questKey, out var cached))
            return cached;

        var projection = QuestPlanProjectionBuilder.Build(GetQuestPlan(questKey), _gameState);
        _planProjectionCache[questKey] = projection;
        return projection;
    }

    public IReadOnlyList<ResolvedQuestTarget> GetTargetsForScene(string questKey, string scene)
    {
        if (_sceneTargetCache.TryGetValue(questKey, out var byScene)
            && byScene.TryGetValue(scene, out var cached))
        {
            return cached;
        }

        var requestedNode = _graph.GetNode(questKey);
        if (requestedNode == null)
            return Array.Empty<ResolvedQuestTarget>();

        var targets = BuildTargets(
            questKey,
            GetQuestPlanProjection(questKey),
            requestedNode,
            sceneFilter: scene);

        if (!_sceneTargetCache.TryGetValue(questKey, out byScene))
        {
            byScene = new Dictionary<string, IReadOnlyList<ResolvedQuestTarget>>(StringComparer.OrdinalIgnoreCase);
            _sceneTargetCache[questKey] = byScene;
        }

        byScene[scene] = targets;
        return targets;
    }

    public IReadOnlyList<ResolvedQuestTarget> ResolveTargetsForNavigation(string nodeKey)
    {
        var requestedNode = _graph.GetNode(nodeKey);
        if (requestedNode == null)
            return Array.Empty<ResolvedQuestTarget>();

        if (requestedNode.Type == NodeType.Quest)
            return ResolveQuest(nodeKey).Targets;

        var plan = _planBuilder.BuildNode(nodeKey);
        return ResolveTargetsForNodePlan(nodeKey, plan, requestedNode);
    }

    public IEnumerable<QuestResolution> ResolveTrackedQuests(IEnumerable<string> trackedQuestDbNames)
    {
        foreach (var dbName in trackedQuestDbNames)
        {
            var resolution = GetQuestResolutionByDbName(dbName);
            if (resolution != null)
                yield return resolution;
        }
    }

    private IReadOnlyList<ResolvedQuestTarget> ResolveTargetsForNodePlan(string nodeKey, QuestPlan plan, Node requestedNode)
    {
        var root = plan.GetNode(plan.RootId) as PlanEntityNode
            ?? throw new InvalidOperationException($"Plan root '{plan.RootId}' missing entity node.");

        var goalContext = CreateContext(root.Node, plan);
        var results = new List<ResolvedQuestTarget>();
        var seen = new HashSet<string>(StringComparer.Ordinal);

        if (requestedNode.Type is NodeType.Item or NodeType.Recipe)
        {
            ResolveItemTargetsFromBlueprint(
                nodeKey, goalContext, requestedNode, results, seen, plan, sceneFilter: null);
            return results;
        }

        if (requestedNode.Type is NodeType.Character or NodeType.ZoneLine)
        {
            var eval = _unlocks.Evaluate(requestedNode);
            if (!eval.IsUnlocked)
            {
                ResolveBlockedTargets(nodeKey, goalContext, requestedNode, eval, results, seen, plan, sceneFilter: null);
                return results;
            }
        }

        var positions = _positionCache.Resolve(requestedNode.Key);
        for (int i = 0; i < positions.Length; i++)
            AddResolvedTargetDirect(results, seen, nodeKey, goalContext, goalContext, positions[i], requestedNode, plan, sceneFilter: null);

        return results;
    }

    private IReadOnlyList<ResolvedQuestTarget> ResolveTargets(
        string questKey,
        QuestPlanProjection projection,
        Node? requestedNode)
    {
        if (_targetCache.TryGetValue(questKey, out var cached))
            return cached;

        using (_dependencies.BeginCollection(new GuideDerivedKey(GuideDerivedKind.QuestTargets, questKey)))
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var targets = BuildTargets(questKey, projection, requestedNode);
            sw.Stop();
            if (sw.Elapsed.TotalMilliseconds >= 5.0)
            {
                var quest = _graph.GetNode(questKey);
                Plugin.Log.LogInfo(
                    $"Targets cold: {quest?.DisplayName ?? questKey}"
                    + $" {sw.Elapsed.TotalMilliseconds:F1}ms"
                    + $" frontier={projection.Frontier.Count} targets={targets.Count}");
            }
            _targetCache[questKey] = targets;
            return targets;
        }
    }

    private IReadOnlyList<ResolvedQuestTarget> BuildTargets(
        string questKey,
        QuestPlanProjection projection,
        Node? requestedNode,
        string? sceneFilter = null)
    {
        if (projection.Frontier.Count == 0 || requestedNode == null)
            return Array.Empty<ResolvedQuestTarget>();

        var results = new List<ResolvedQuestTarget>();
        var seen = new HashSet<string>(StringComparer.Ordinal);

        for (int i = 0; i < projection.Frontier.Count; i++)
        {
            var frontierRef = projection.Frontier[i];
            var frontierNode = projection.Plan.GetNode(frontierRef.NodeId) as PlanEntityNode;
            if (frontierNode == null)
                continue;

            var goalContext = ToContext(frontierRef, projection.Plan);
            var nodeType = frontierNode.Node.Type;

            if (nodeType is NodeType.Item or NodeType.Recipe)
            {
                ResolveItemTargetsFromBlueprint(
                    questKey, goalContext, requestedNode, results, seen, projection.Plan, sceneFilter);
                continue;
            }

            if (nodeType == NodeType.Quest)
            {
                var prereqTargets = sceneFilter == null
                    ? ResolveQuest(frontierNode.NodeKey).Targets
                    : GetTargetsForScene(frontierNode.NodeKey, sceneFilter);
                foreach (var t in prereqTargets)
                    results.Add(new ResolvedQuestTarget(
                        t.TargetNodeKey, t.Scene, t.SourceKey,
                        t.GoalNode, t.TargetNode, t.Semantic, t.Explanation,
                        t.X, t.Y, t.Z, t.IsActionable,
                        // Tag with the sub-quest key so the tracker can show
                        // "Needed for <sub-quest>" in its secondary line.
                        requiredForQuestKey: frontierNode.NodeKey));
                continue;
            }

            if (nodeType is NodeType.Character or NodeType.ZoneLine)
            {
                var eval = _unlocks.Evaluate(frontierNode.Node);
                if (!eval.IsUnlocked)
                {
                    ResolveBlockedTargets(
                        questKey, goalContext, requestedNode, eval, results, seen, projection.Plan, sceneFilter);
                    continue;
                }
            }

            var positions = _positionCache.Resolve(frontierNode.NodeKey);
            for (int j = 0; j < positions.Length; j++)
                AddResolvedTargetDirect(
                    results, seen, questKey, goalContext, goalContext, positions[j], requestedNode, projection.Plan, sceneFilter);
        }

        return results;
    }

    private void ResolveBlockedTargets(
        string questKey,
        ResolvedNodeContext frontierNode,
        Node requestedNode,
        UnlockEvaluation evaluation,
        List<ResolvedQuestTarget> results,
        HashSet<string> seen,
        QuestPlan? plan,
        string? sceneFilter)
    {
        var blocking = evaluation.BlockingSources;
        for (int i = 0; i < blocking.Count; i++)
        {
            var blockingSource = blocking[i];
            if (blockingSource.Type == NodeType.Quest)
            {
                if (string.Equals(blockingSource.Key, questKey, StringComparison.Ordinal))
                    continue;

                // Deduplicate: the same blocking quest may be reached via
                // multiple blocked-route paths (e.g. ten out-of-zone fishing
                // spots all gated behind the same prerequisite). Expanding
                // once per (parent quest, goal context, blocking quest, scene
                // filter) is sufficient; further copies produce identical tagged
                // targets.
                string expansionKey =
                    $"bq|{questKey}|{frontierNode.NodeKey}|{blockingSource.Key}|{sceneFilter ?? string.Empty}";
                if (!seen.Add(expansionKey))
                    continue;

                var blockingTargets = sceneFilter == null
                    ? ResolveQuest(blockingSource.Key).Targets
                    : GetTargetsForScene(blockingSource.Key, sceneFilter);
                foreach (var t in blockingTargets)
                    results.Add(new ResolvedQuestTarget(
                        t.TargetNodeKey, t.Scene, t.SourceKey,
                        t.GoalNode, t.TargetNode, t.Semantic, t.Explanation,
                        t.X, t.Y, t.Z, t.IsActionable,
                        requiredForQuestKey: blockingSource.Key));
                continue;
            }

            if (blockingSource.Type is NodeType.Item or NodeType.Recipe)
            {
                var itemContext = CreateContext(blockingSource, plan);
                ResolveItemTargetsFromBlueprint(
                    questKey, itemContext, requestedNode, results, seen, plan, sceneFilter);
                continue;
            }

            if (blockingSource.Type == NodeType.Door)
            {
                var doorState = _gameState.GetState(blockingSource.Key);
                if (doorState is DoorLocked)
                {
                    var doorEvaluation = _unlocks.Evaluate(blockingSource);
                    if (!doorEvaluation.IsUnlocked)
                    {
                        ResolveBlockedTargets(
                            questKey, frontierNode, requestedNode, doorEvaluation, results, seen, plan, sceneFilter);
                        continue;
                    }
                }
            }

            var blockingContext = CreateContext(blockingSource, plan);
            var positions = _positionCache.Resolve(blockingSource.Key);
            for (int j = 0; j < positions.Length; j++)
                AddResolvedTargetDirect(
                    results, seen, questKey, frontierNode, blockingContext, positions[j], requestedNode, plan, sceneFilter);
        }
    }

    private void ResolveItemTargetsFromBlueprint(
        string questKey,
        ResolvedNodeContext frontierNode,
        Node requestedNode,
        List<ResolvedQuestTarget> results,
        HashSet<string> seen,
        QuestPlan? plan,
        string? sceneFilter)
    {
        IReadOnlyList<SourceSiteBlueprint> sources;
        if (sceneFilter == null)
        {
            sources = _sourceIndex.GetSourceSitesForItem(frontierNode.NodeKey);
        }
        else
        {
            var allSites = _sourceIndex.GetSourceSitesForItem(frontierNode.NodeKey);
            var currentSceneSites = _sourceIndex.GetSourceSitesForItemInScene(frontierNode.NodeKey, sceneFilter);
            var reduced = new List<SourceSiteBlueprint>(currentSceneSites.Count + 8);
            var addedIds = new HashSet<string>(StringComparer.Ordinal);
            var addedScenes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            for (int i = 0; i < currentSceneSites.Count; i++)
            {
                var site = currentSceneSites[i];
                reduced.Add(site);
                addedIds.Add(SourceSiteBlueprint.BuildId(site.SourceNodeKey, site.AcquisitionEdge, site.Scene, site.DirectItemKey));
                if (!string.IsNullOrEmpty(site.Scene))
                    addedScenes.Add(site.Scene);
            }

            for (int i = 0; i < allSites.Count; i++)
            {
                var site = allSites[i];
                string siteId = SourceSiteBlueprint.BuildId(site.SourceNodeKey, site.AcquisitionEdge, site.Scene, site.DirectItemKey);
                if (addedIds.Contains(siteId))
                    continue;
                if (string.IsNullOrEmpty(site.Scene))
                {
                    reduced.Add(site);
                    addedIds.Add(siteId);
                    continue;
                }
                if (!addedScenes.Add(site.Scene))
                    continue;

                reduced.Add(site);
                addedIds.Add(siteId);
            }

            sources = reduced;
        }

        if (sources.Count == 0)
            return;

        bool hasReachable = false;
        for (int i = 0; i < sources.Count; i++)
        {
            if (IsSourceReachable(sources[i]))
            {
                hasReachable = true;
                break;
            }
        }

        for (int i = 0; i < sources.Count; i++)
        {
            var source = sources[i];
            var sourceNode = _graph.GetNode(source.SourceNodeKey);
            if (sourceNode == null)
                continue;

            if (source.SourceNodeType == NodeType.Quest
                && _gameState.GetState(source.SourceNodeKey) is QuestCompleted)
            {
                continue;
            }

            bool reachable = IsSourceReachable(source);
            if (hasReachable && !reachable)
                continue;

            if (!reachable && sourceNode.Type is NodeType.Character or NodeType.ZoneLine)
            {
                var evaluation = _unlocks.Evaluate(sourceNode);
                if (!evaluation.IsUnlocked)
                {
                    ResolveBlockedTargets(
                        questKey, frontierNode, requestedNode, evaluation, results, seen, plan, sceneFilter);
                    continue;
                }
            }

            ResolvedPosition[] positions;
            if (sceneFilter != null)
            {
                if (string.Equals(source.Scene, sceneFilter, StringComparison.OrdinalIgnoreCase))
                {
                    positions = _positionCache.Resolve(source.SourceNodeKey)
                        .Where(pos => string.Equals(pos.Scene, sceneFilter, StringComparison.OrdinalIgnoreCase))
                        .ToArray();
                }
                else
                {
                    var representative = GetRepresentativePosition(source);
                    positions = representative == null ? Array.Empty<ResolvedPosition>() : new[] { representative.Value };
                }
            }
            else
            {
                positions = _positionCache.Resolve(source.SourceNodeKey);
            }

            if (positions.Length == 0)
                continue;

            var targetContext = CreateContext(sourceNode, source.AcquisitionEdge, plan);
            // Use the direct item as goalNode when the source is a transitive recipe
            // ingredient. BuildRationaleText reads goalNode.Node.DisplayName for the
            // "Drops / Sells / Yields X" text — that must be the item this specific
            // source provides (e.g. Iron Ore), not the root crafted item (Ghostly Key).
            var directItemNode = _graph.GetNode(source.DirectItemKey);
            var directGoalNode = directItemNode != null
                && !string.Equals(source.DirectItemKey, frontierNode.NodeKey, StringComparison.Ordinal)
                ? CreateContext(directItemNode, plan)
                : frontierNode;
            for (int j = 0; j < positions.Length; j++)
                AddResolvedTargetDirect(
                    results, seen, questKey, directGoalNode, targetContext, positions[j], requestedNode, plan, sceneFilter);
        }
    }
    private bool TryResolveBlockedRoute(
        List<ResolvedQuestTarget> results,
        HashSet<string> seen,
        string questKey,
        ResolvedNodeContext goalNode,
        ResolvedNodeContext targetNode,
        ResolvedPosition pos,
        Node requestedNode,
        QuestPlan? plan,
        string? sceneFilter)
    {
        string? targetScene = GetBlockedRouteScene(targetNode, pos);
        var blockedRoute = _zoneAccess.FindBlockedRoute(targetScene);
        if (blockedRoute == null)
            return false;

        string routeDedupeKey = string.Join("|", new[]
        {
            "route",
            questKey,
            goalNode.NodeKey,
            targetScene ?? string.Empty,
            blockedRoute.ZoneLineNode.Key,
        });
        if (!seen.Add(routeDedupeKey))
            return true;

        ResolveBlockedTargets(
            questKey,
            goalNode,
            requestedNode,
            blockedRoute.Evaluation,
            results,
            seen,
            plan,
            sceneFilter);
        return true;
    }

    private static string? GetBlockedRouteScene(ResolvedNodeContext targetNode, ResolvedPosition pos)
    {
        if (targetNode.Node.Type == NodeType.Zone && !string.IsNullOrEmpty(targetNode.Node.Scene))
            return targetNode.Node.Scene;

        return pos.Scene ?? targetNode.Node.Scene;
    }

    private void AddResolvedTargetDirect(
        List<ResolvedQuestTarget> results,
        HashSet<string> seen,
        string questKey,
        ResolvedNodeContext goalNode,
        ResolvedNodeContext targetNode,
        ResolvedPosition pos,
        Node requestedNode,
        QuestPlan? plan,
        string? sceneFilter)
    {
        if (TryResolveBlockedRoute(results, seen, questKey, goalNode, targetNode, pos, requestedNode, plan, sceneFilter))
            return;

        if (sceneFilter != null && !string.Equals(pos.Scene, sceneFilter, StringComparison.OrdinalIgnoreCase))
            return;

        string dedupeKey = string.Join("|", new[]
        {
            questKey,
            targetNode.NodeKey,
            pos.Scene ?? string.Empty,
            pos.SourceKey ?? string.Empty,
            goalNode.NodeKey,
        });

        if (!seen.Add(dedupeKey))
            return;

        var semantic = ResolvedActionSemanticBuilder.Build(
            _graph,
            requestedNode,
            goalNode,
            targetNode);
        var explanation = NavigationExplanationBuilder.Build(
            semantic,
            goalNode,
            targetNode);

        results.Add(new ResolvedQuestTarget(
            targetNode.NodeKey,
            pos.Scene,
            pos.SourceKey,
            goalNode,
            targetNode,
            semantic,
            explanation,
            pos.Position.x, pos.Position.y, pos.Position.z,
            pos.IsActionable));
    }

    // ── Blocked-target resolution ────────────────────────────────────────────

    /// <summary>
    /// When a frontier node is unlock-blocked, resolve positions for its
    /// blocking sources so navigation reaches the unlock requirement instead.
    /// </summary>

    private bool IsSourceReachable(SourceSiteBlueprint source)
    {
        if (source.SourceNodeType != NodeType.Character)
            return true;

        var sourceNode = _graph.GetNode(source.SourceNodeKey);
        if (sourceNode == null)
            return false;

        var eval = _unlocks.Evaluate(sourceNode);
        return eval.IsUnlocked;
    }

    private static ResolvedPosition? GetRepresentativePosition(SourceSiteBlueprint source)
    {
        if (source.StaticPositions.Count == 0)
            return null;

        var pos = source.StaticPositions[0];
        return new ResolvedPosition(
            new Vector3(pos.X, pos.Y, pos.Z),
            pos.Scene,
            pos.PositionNodeKey);
    }


    private TrackerSummary BuildTrackerSummary(
        Node? requestedNode,
        string questKey,
        QuestPlanProjection projection,
        IReadOnlyList<ResolvedQuestTarget> targets)
    {
        if (projection.Frontier.Count == 0)
            return new TrackerSummary("Ready to turn in", null);

        var focusTarget = SelectTrackerFocusTarget(targets);
        var frontierContext = focusTarget?.GoalNode
            ?? ToContext(projection.Frontier[0], projection.Plan);
        var summarySemantic = focusTarget?.Semantic
            ?? ResolvedActionSemanticBuilder.Build(
                _graph,
                requestedNode ?? frontierContext.Node,
                frontierContext,
                frontierContext);

        // Derive the "Needed for" context from the plan resolution chain, not from
        // graph-level prerequisite edges. When the focus target is a step toward a
        // sub-quest, RequiredForQuestKey holds that sub-quest's key; show its name.
        // For direct steps of the tracked quest RequiredForQuestKey is null — the
        // quest header already provides the context, no secondary needed.
        string? neededForContext = null;
        if (focusTarget?.RequiredForQuestKey != null)
            neededForContext = _graph.GetNode(focusTarget.RequiredForQuestKey)?.DisplayName;

        return NavigationExplanationBuilder.BuildTrackerSummary(
            frontierContext,
            summarySemantic,
            _tracker,
            Math.Max(0, projection.Frontier.Count - 1),
            neededForContext);
    }

    private ResolvedQuestTarget? SelectTrackerFocusTarget(IReadOnlyList<ResolvedQuestTarget> targets)
    {
        if (targets.Count == 0)
            return null;

        var best = targets[0];
        for (int i = 1; i < targets.Count; i++)
        {
            if (IsBetterTrackerTarget(targets[i], best))
                best = targets[i];
        }

        return best;
    }

    private bool IsBetterTrackerTarget(ResolvedQuestTarget candidate, ResolvedQuestTarget currentBest)
    {
        // Prefer direct targets over those on blocked-but-feasible routes.
        // Within the same blocking status existing criteria still apply, so
        // blocked-path in-zone beats blocked-path cross-zone.
        bool candidateBlocked = candidate.IsBlockedPath;
        bool currentBlocked   = currentBest.IsBlockedPath;
        if (candidateBlocked != currentBlocked)
            return !candidateBlocked;

        int candidateSceneRank = GetTrackerSceneRank(candidate);
        int currentSceneRank = GetTrackerSceneRank(currentBest);
        if (candidateSceneRank != currentSceneRank)
            return candidateSceneRank < currentSceneRank;

        if (candidate.IsActionable != currentBest.IsActionable)
            return candidate.IsActionable;

        int candidateHops = GetTrackerHopCount(candidate);
        int currentHops = GetTrackerHopCount(currentBest);
        if (candidateHops != currentHops)
            return candidateHops < currentHops;

        var player = GameData.PlayerControl;
        bool sameScene = IsTrackerCurrentScene(candidate);
        bool currentSameScene = IsTrackerCurrentScene(currentBest);
        if (player != null && sameScene && currentSameScene)
        {
            var pp = player.transform.position;
            float candidateDistance = (candidate.X - pp.x) * (candidate.X - pp.x)
                + (candidate.Y - pp.y) * (candidate.Y - pp.y)
                + (candidate.Z - pp.z) * (candidate.Z - pp.z);
            float currentDistance = (currentBest.X - pp.x) * (currentBest.X - pp.x)
                + (currentBest.Y - pp.y) * (currentBest.Y - pp.y)
                + (currentBest.Z - pp.z) * (currentBest.Z - pp.z);
            if (!Mathf.Approximately(candidateDistance, currentDistance))
                return candidateDistance < currentDistance;
        }

        return false;
    }

    private int GetTrackerSceneRank(ResolvedQuestTarget target)
    {
        if (IsTrackerCurrentScene(target))
            return 0;
        if (string.IsNullOrEmpty(target.Scene))
            return 1;
        return _router.FindRoute(_tracker.CurrentZone, target.Scene!) != null ? 1 : 2;
    }

    private int GetTrackerHopCount(ResolvedQuestTarget target)
    {
        if (IsTrackerCurrentScene(target) || string.IsNullOrEmpty(target.Scene))
            return 0;

        var route = _router.FindRoute(_tracker.CurrentZone, target.Scene!);
        return route == null ? int.MaxValue : Math.Max(0, route.Path.Count - 1);
    }

    private bool IsTrackerCurrentScene(ResolvedQuestTarget target) =>
        string.IsNullOrEmpty(target.Scene)
        || string.Equals(target.Scene, _tracker.CurrentZone, StringComparison.OrdinalIgnoreCase);

    private static ResolvedNodeContext ToContext(FrontierRef frontierRef, QuestPlan plan)
    {
        var node = (PlanEntityNode)(plan.GetNode(frontierRef.NodeId)
            ?? throw new InvalidOperationException($"Plan node '{frontierRef.NodeId}' not found."));
        return new ResolvedNodeContext(
            node.NodeKey,
            node.Node,
            frontierRef.IncomingLink.EdgeType,
            frontierRef.IncomingLink.Quantity,
            frontierRef.IncomingLink.Keyword,
            node.SourceZones,
            node.EffectiveLevel);
    }

    private static ResolvedNodeContext CreateContext(Node node, QuestPlan? plan = null)
        => CreateContext(node, edgeType: null, plan);

    private static ResolvedNodeContext CreateContext(Node node, EdgeType? edgeType, QuestPlan? plan)
    {
        if (plan != null && plan.EntityNodesByKey.TryGetValue(node.Key, out var planNode))
        {
            return new ResolvedNodeContext(
                planNode.NodeKey,
                planNode.Node,
                edgeType,
                quantity: null,
                keyword: null,
                planNode.SourceZones,
                planNode.EffectiveLevel);
        }

        return new ResolvedNodeContext(
            node.Key,
            node,
            edgeType);
    }
}
