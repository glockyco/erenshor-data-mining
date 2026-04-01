using AdventureGuide.Plan;
using AdventureGuide.Graph;
using AdventureGuide.Navigation;
using AdventureGuide.Position;
using AdventureGuide.State;

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

    private readonly Dictionary<string, QuestPlan> _planCache = new(StringComparer.Ordinal);
    private readonly Dictionary<string, QuestPlanProjection> _planProjectionCache = new(StringComparer.Ordinal);
    private readonly Dictionary<string, IReadOnlyList<ResolvedQuestTarget>> _targetCache = new(StringComparer.Ordinal);

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
    }

    public GuideChangeSet ApplyChangeSet(GuideChangeSet changeSet)
    {
        if (changeSet == null || !changeSet.HasMeaningfulChanges)
            return GuideChangeSet.None;

        if (changeSet.SceneChanged)
        {
            if (_planCache.Count > 0 || _planProjectionCache.Count > 0 || _targetCache.Count > 0)
            {
                _planCache.Clear();
                _planProjectionCache.Clear();
                _targetCache.Clear();
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
                case GuideDerivedKind.QuestStructure:
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
        var projection = GetQuestPlanProjection(questKey);
        var questNode = _graph.GetNode(questKey);
        var targets = ResolveTargets(questKey, projection, questNode);
        var trackerSummary = BuildTrackerSummary(questNode, questKey, projection, targets);

        return new QuestResolution(
            questKey,
            projection,
            targets,
            trackerSummary);
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
            ResolveItemTargetsFromBlueprint(nodeKey, goalContext, requestedNode, results, seen);
            return results;
        }

        if (requestedNode.Type is NodeType.Character or NodeType.ZoneLine)
        {
            var eval = _unlocks.Evaluate(requestedNode);
            if (!eval.IsUnlocked)
            {
                ResolveBlockedTargets(nodeKey, goalContext, requestedNode, eval, results, seen, plan);
                return results;
            }
        }

        var positions = _positionCache.Resolve(requestedNode.Key);
        for (int i = 0; i < positions.Length; i++)
            AddResolvedTargetDirect(results, seen, nodeKey, goalContext, goalContext, positions[i], requestedNode);

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
        Node? requestedNode)
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
                    questKey, goalContext, requestedNode, results, seen);
                continue;
            }

            if (nodeType == NodeType.Quest)
            {
                var prereqResolution = ResolveQuest(frontierNode.NodeKey);
                foreach (var t in prereqResolution.Targets)
                    results.Add(new ResolvedQuestTarget(
                        questKey, t.TargetNodeKey, t.Scene, t.SourceKey,
                        t.GoalNode, t.TargetNode, t.Semantic, t.Explanation,
                        t.Position, t.IsActionable));
                continue;
            }

            if (nodeType is NodeType.Character or NodeType.ZoneLine)
            {
                var eval = _unlocks.Evaluate(frontierNode.Node);
                if (!eval.IsUnlocked)
                {
                    ResolveBlockedTargets(questKey, goalContext, requestedNode, eval, results, seen, projection.Plan);
                    continue;
                }
            }

            var positions = _positionCache.Resolve(frontierNode.NodeKey);
            for (int j = 0; j < positions.Length; j++)
                AddResolvedTargetDirect(results, seen, questKey,
                    goalContext, goalContext, positions[j], requestedNode);
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
        QuestPlan plan)
    {
        var blocking = evaluation.BlockingSources;
        for (int i = 0; i < blocking.Count; i++)
        {
            var blockingSource = blocking[i];
            if (blockingSource.Type == NodeType.Quest)
            {
                var blockingResolution = ResolveQuest(blockingSource.Key);
                foreach (var t in blockingResolution.Targets)
                    results.Add(new ResolvedQuestTarget(
                        questKey, t.TargetNodeKey, t.Scene, t.SourceKey,
                        t.GoalNode, t.TargetNode, t.Semantic, t.Explanation,
                        t.Position, t.IsActionable));
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
                        ResolveBlockedTargets(questKey, frontierNode, requestedNode, doorEvaluation, results, seen, plan);
                        continue;
                    }
                }
            }

            var blockingContext = CreateContext(blockingSource, plan);
            var positions = _positionCache.Resolve(blockingSource.Key);
            for (int j = 0; j < positions.Length; j++)
                AddResolvedTargetDirect(results, seen, questKey,
                    frontierNode, blockingContext, positions[j], requestedNode);
        }
    }

    private void ResolveItemTargetsFromBlueprint(
        string questKey,
        ResolvedNodeContext frontierNode,
        Node requestedNode,
        List<ResolvedQuestTarget> results,
        HashSet<string> seen)
    {
        var sources = _sourceIndex.GetSourcesForItem(frontierNode.NodeKey);
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
            if (sourceNode == null) continue;

            if (source.SourceNodeType == NodeType.Quest
                && _gameState.GetState(source.SourceNodeKey) is QuestCompleted)
                continue;

            bool reachable = IsSourceReachable(source);
            if (hasReachable && !reachable)
                continue;

            var positions = _positionCache.Resolve(source.SourceNodeKey);
            if (positions.Length == 0) continue;

            var targetContext = CreateContext(sourceNode, source.AcquisitionEdge, plan: null);
            for (int j = 0; j < positions.Length; j++)
                AddResolvedTargetDirect(results, seen, questKey,
                    frontierNode, targetContext, positions[j], requestedNode);
        }
    }

    private void AddResolvedTargetDirect(
        List<ResolvedQuestTarget> results,
        HashSet<string> seen,
        string questKey,
        ResolvedNodeContext goalNode,
        ResolvedNodeContext targetNode,
        ResolvedPosition pos,
        Node requestedNode)
    {
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
            questKey,
            targetNode.NodeKey,
            pos.Scene,
            pos.SourceKey,
            goalNode,
            targetNode,
            semantic,
            explanation,
            pos.Position,
            pos.IsActionable));
    }

    // ── Blocked-target resolution ────────────────────────────────────────────

    /// <summary>
    /// When a frontier node is unlock-blocked, resolve positions for its
    /// blocking sources so navigation reaches the unlock requirement instead.
    /// </summary>

    private bool IsSourceReachable(SourceEntry source)
    {
        if (source.SourceNodeType != NodeType.Character)
            return true;

        var sourceNode = _graph.GetNode(source.SourceNodeKey);
        if (sourceNode == null) return false;

        var eval = _unlocks.Evaluate(sourceNode);
        return eval.IsUnlocked;
    }


    private TrackerSummary BuildTrackerSummary(
        Node? requestedNode,
        string questKey,
        QuestPlanProjection projection,
        IReadOnlyList<ResolvedQuestTarget> targets)
    {
        if (projection.Frontier.Count == 0)
            return new TrackerSummary("Ready to turn in", null);

        var frontierContext = ToContext(projection.Frontier[0], projection.Plan);
        var summarySemantic = SelectTrackerSemantic(projection.Frontier[0], projection.Plan, targets)
            ?? ResolvedActionSemanticBuilder.Build(
                _graph,
                requestedNode ?? frontierContext.Node,
                frontierContext,
                frontierContext);

        string? prerequisiteQuestName = FindFirstIncompletePrerequisite(questKey);

        return NavigationExplanationBuilder.BuildTrackerSummary(
            frontierContext,
            summarySemantic,
            _tracker,
            Math.Max(0, projection.Frontier.Count - 1),
            prerequisiteQuestName);
    }

    private string? FindFirstIncompletePrerequisite(string questKey)
    {
        foreach (var edge in _graph.OutEdges(questKey, EdgeType.RequiresQuest))
        {
            if (_gameState.GetState(edge.Target) is not QuestCompleted)
                return _graph.GetNode(edge.Target)?.DisplayName;
        }
        foreach (var edge in _graph.OutEdges(questKey, EdgeType.AssignedBy))
        {
            var node = _graph.GetNode(edge.Target);
            if (node?.Type == NodeType.Quest
                && _gameState.GetState(edge.Target) is not QuestCompleted)
                return node.DisplayName;
        }
        return null;
    }

    private static ResolvedActionSemantic? SelectTrackerSemantic(
        FrontierRef frontierNode,
        QuestPlan plan,
        IReadOnlyList<ResolvedQuestTarget> targets)
    {
        for (int i = 0; i < targets.Count; i++)
        {
            if (IsSameGoal(frontierNode, targets[i].GoalNode))
                return targets[i].Semantic;
        }

        return targets.Count > 0 ? targets[0].Semantic : null;
    }

    private static bool IsSameGoal(FrontierRef frontierNode, ResolvedNodeContext candidateGoal)
    {
        if (frontierNode.IncomingLink.EdgeType != candidateGoal.EdgeType)
            return false;

        return frontierNode.GoalId.Value == candidateGoal.NodeKey;
    }

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
