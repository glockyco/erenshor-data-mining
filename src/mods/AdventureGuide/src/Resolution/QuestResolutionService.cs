using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using AdventureGuide.Views;
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
    private readonly QuestViewBuilder _viewBuilder;
    private readonly ViewNodePositionCollector _viewPositions;
    private readonly GuideDependencyEngine _dependencies;
    private readonly CompiledSourceIndex _sourceIndex;
    private readonly SourcePositionCache _positionCache;
    private readonly UnlockEvaluator _unlocks;

    private readonly Dictionary<string, QuestStructure> _structureCache = new(StringComparer.Ordinal);
    private readonly Dictionary<string, IReadOnlyList<ResolvedQuestTarget>> _targetCache = new(StringComparer.Ordinal);
    private readonly List<ResolvedViewPosition> _detailedPositions = new();

    public int Version { get; private set; }

    public QuestResolutionService(
        EntityGraph graph,
        QuestStateTracker tracker,
        GameState gameState,
        QuestViewBuilder viewBuilder,
        ViewNodePositionCollector viewPositions,
        GuideDependencyEngine dependencies,
        CompiledSourceIndex sourceIndex,
        SourcePositionCache positionCache,
        UnlockEvaluator unlocks)
    {
        _graph = graph;
        _tracker = tracker;
        _gameState = gameState;
        _viewBuilder = viewBuilder;
        _viewPositions = viewPositions;
        _dependencies = dependencies;
        _sourceIndex = sourceIndex;
        _positionCache = positionCache;
        _unlocks = unlocks;
    }

    public GuideChangeSet ApplyChangeSet(GuideChangeSet changeSet)
    {
        if (changeSet == null || !changeSet.HasMeaningfulChanges)
            return GuideChangeSet.None;

        if (changeSet.SceneChanged)
        {
            if (_structureCache.Count > 0 || _targetCache.Count > 0)
            {
                _structureCache.Clear();
                _targetCache.Clear();
                _dependencies.Clear();
                _positionCache.Clear();
                Version++;
            }

            return changeSet;
        }

        var structureInvalidations = new HashSet<string>(StringComparer.Ordinal);
        var targetInvalidations = new HashSet<string>(changeSet.AffectedQuestKeys, StringComparer.Ordinal);

        bool staticStructureChange = changeSet.InventoryChanged || changeSet.QuestLogChanged;

        foreach (var derivedKey in _dependencies.InvalidateFacts(changeSet.ChangedFacts))
        {
            switch (derivedKey.Kind)
            {
                case GuideDerivedKind.QuestStructure:
                    structureInvalidations.Add(derivedKey.Key);
                    targetInvalidations.Add(derivedKey.Key);
                    break;
                case GuideDerivedKind.QuestTargets:
                    targetInvalidations.Add(derivedKey.Key);
                    break;
            }
        }

        if (staticStructureChange)
            structureInvalidations.UnionWith(changeSet.AffectedQuestKeys);

        bool removedAny = false;
        foreach (var questKey in structureInvalidations)
            removedAny |= _structureCache.Remove(questKey);

        foreach (var questKey in targetInvalidations)
            removedAny |= _targetCache.Remove(questKey);


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
        var structure = ResolveStructure(questKey);
        var questNode = _graph.GetNode(questKey);
        var targets = ResolveTargets(questKey, structure.Frontier, questNode);
        var trackerSummary = BuildTrackerSummary(questNode, structure.ViewRoot, structure.Frontier, targets);

        return new QuestResolution(
            questKey,
            structure.ViewRoot,
            structure.Frontier,
            targets,
            trackerSummary);
    }

    public IReadOnlyList<ResolvedQuestTarget> ResolveTargetsForNavigation(string nodeKey, EntityViewNode? context = null)
    {
        var requestedNode = _graph.GetNode(nodeKey);
        if (requestedNode == null && context == null)
            return Array.Empty<ResolvedQuestTarget>();

        if (context != null)
            return CollectTargets(nodeKey, context, requestedNode ?? context.Node);

        if (requestedNode!.Type == NodeType.Quest)
            return ResolveQuest(nodeKey).Targets;

        var root = requestedNode.Type == NodeType.Item || requestedNode.Type == NodeType.Recipe
            ? _viewBuilder.BuildNode(nodeKey)
            : new EntityViewNode(nodeKey, requestedNode);

        return root == null
            ? Array.Empty<ResolvedQuestTarget>()
            : CollectTargets(nodeKey, root, requestedNode);
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

    private QuestStructure ResolveStructure(string questKey)
    {
        if (_structureCache.TryGetValue(questKey, out var cached))
            return cached;

        using (_dependencies.BeginCollection(new GuideDerivedKey(GuideDerivedKind.QuestStructure, questKey)))
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var root = _viewBuilder.Build(questKey);
            var buildMs = sw.Elapsed.TotalMilliseconds;
            sw.Restart();
            var frontier = root != null
                ? FrontierComputer.ComputeFrontier(root, _gameState)
                : new List<EntityViewNode>();
            var frontierMs = sw.Elapsed.TotalMilliseconds;

            if (buildMs + frontierMs >= 5.0)
            {
                var quest = _graph.GetNode(questKey);
                Plugin.Log.LogInfo(
                    $"Structure cold: {quest?.DisplayName ?? questKey}"
                    + $" build={buildMs:F1}ms frontier={frontierMs:F1}ms");
            }

            var structure = new QuestStructure(root, frontier);
            _structureCache[questKey] = structure;
            return structure;
        }
    }

    private IReadOnlyList<ResolvedQuestTarget> ResolveTargets(
        string questKey,
        IReadOnlyList<EntityViewNode> frontier,
        Node? requestedNode)
    {
        if (_targetCache.TryGetValue(questKey, out var cached))
            return cached;

        using (_dependencies.BeginCollection(new GuideDerivedKey(GuideDerivedKind.QuestTargets, questKey)))
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var targets = BuildTargets(questKey, frontier, requestedNode);
            sw.Stop();
            if (sw.Elapsed.TotalMilliseconds >= 5.0)
            {
                var quest = _graph.GetNode(questKey);
                Plugin.Log.LogInfo(
                    $"Targets cold: {quest?.DisplayName ?? questKey}"
                    + $" {sw.Elapsed.TotalMilliseconds:F1}ms"
                    + $" frontier={frontier.Count} targets={targets.Count}");
            }
            _targetCache[questKey] = targets;
            return targets;
        }
    }

    private IReadOnlyList<ResolvedQuestTarget> BuildTargets(
        string questKey,
        IReadOnlyList<EntityViewNode> frontier,
        Node? requestedNode)
    {
        if (frontier.Count == 0 || requestedNode == null)
            return Array.Empty<ResolvedQuestTarget>();

        var results = new List<ResolvedQuestTarget>();
        var seen = new HashSet<string>(StringComparer.Ordinal);

        for (int i = 0; i < frontier.Count; i++)
        {
            var frontierNode = frontier[i];

            // Item/Recipe frontier nodes are the expensive case: they recurse
            // into potentially hundreds of source children. Use the pre-compiled
            // source index instead of walking the view tree.
            if (frontierNode.Node.Type is NodeType.Item or NodeType.Recipe)
            {
                ResolveItemTargetsFromBlueprint(
                    questKey, frontierNode, requestedNode, results, seen);
                continue;
            }

            // All other frontier node types (Character, Zone, Quest, etc.)
            // use the view-tree-based collector. It benefits from the shared
            // SourcePositionCache for leaf position resolution.
            _detailedPositions.Clear();
            _viewPositions.CollectDetailed(frontierNode, _detailedPositions);
            for (int j = 0; j < _detailedPositions.Count; j++)
                AddResolvedTarget(results, seen, questKey, _detailedPositions[j], requestedNode);
        }

        return results;
    }

    // ── Blueprint-based item target resolution ──────────────────────────────

    /// <summary>
    /// Resolve targets for an item/recipe frontier node using the pre-compiled
    /// source index. This avoids the recursive view-tree walk that previously
    /// dominated cold-path cost for quests with broad item dependencies.
    /// </summary>
    private void ResolveItemTargetsFromBlueprint(
        string questKey,
        EntityViewNode frontierNode,
        Node requestedNode,
        List<ResolvedQuestTarget> results,
        HashSet<string> seen)
    {
        var sources = _sourceIndex.GetSourcesForItem(frontierNode.NodeKey);
        if (sources.Count == 0)
        {
            // No pre-compiled sources — fall back to view-tree walk.
            // This handles edge cases where the view builder found sources
            // that the static compilation missed (e.g., dynamic item paths).
            _detailedPositions.Clear();
            _viewPositions.CollectDetailed(frontierNode, _detailedPositions);
            for (int i = 0; i < _detailedPositions.Count; i++)
                AddResolvedTarget(results, seen, questKey, _detailedPositions[i], requestedNode);
            return;
        }

        // Determine if any source is reachable (not unlock-blocked).
        // When reachable sources exist, skip blocked alternatives so they
        // cannot override usable direct sources during candidate selection.
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

            // Skip completed quest reward sources — the reward is already received.
            if (source.SourceNodeType == NodeType.Quest
                && _gameState.GetState(source.SourceNodeKey) is QuestCompleted)
                continue;

            bool reachable = IsSourceReachable(source);
            if (hasReachable && !reachable)
                continue;

            // Resolve positions from cache.
            var positions = _positionCache.Resolve(source.SourceNodeKey);
            if (positions.Length == 0) continue;

            // Create a synthetic target view node for attribution.
            // ResolvedActionSemanticBuilder needs the node reference and edge type.
            var targetViewNode = new EntityViewNode(
                source.SourceNodeKey, sourceNode, source.AcquisitionEdge, null);

            for (int j = 0; j < positions.Length; j++)
            {
                var pos = positions[j];
                var resolved = new ResolvedViewPosition(
                    pos.Position, pos.Scene, pos.SourceKey,
                    frontierNode, targetViewNode, pos.IsActionable);
                AddResolvedTarget(results, seen, questKey, resolved, requestedNode);
            }
        }
    }

    private bool IsSourceReachable(SourceEntry source)
    {
        if (source.SourceNodeType != NodeType.Character)
            return true;

        var sourceNode = _graph.GetNode(source.SourceNodeKey);
        if (sourceNode == null) return false;

        var eval = _unlocks.Evaluate(sourceNode);
        return eval.IsUnlocked;
    }

    private IReadOnlyList<ResolvedQuestTarget> CollectTargets(string questKey, ViewNode root, Node requestedNode)
    {
        var results = new List<ResolvedQuestTarget>();
        var seen = new HashSet<string>(StringComparer.Ordinal);

        _detailedPositions.Clear();
        _viewPositions.CollectDetailed(root, _detailedPositions);
        for (int i = 0; i < _detailedPositions.Count; i++)
            AddResolvedTarget(results, seen, questKey, _detailedPositions[i], requestedNode);

        return results;
    }

    private void AddResolvedTarget(
        List<ResolvedQuestTarget> results,
        HashSet<string> seen,
        string questKey,
        ResolvedViewPosition resolved,
        Node requestedNode)
    {
        string dedupeKey = string.Join("|", new[]
        {
            questKey,
            resolved.TargetNode.NodeKey,
            resolved.Scene ?? string.Empty,
            resolved.SourceKey ?? string.Empty,
            resolved.GoalNode.NodeKey,
        });

        if (!seen.Add(dedupeKey))
            return;

        var semantic = ResolvedActionSemanticBuilder.Build(
            _graph,
            requestedNode,
            resolved.GoalNode,
            resolved.TargetNode);
        var explanation = NavigationExplanationBuilder.Build(
            semantic,
            resolved.GoalNode,
            resolved.TargetNode);

        results.Add(new ResolvedQuestTarget(
            questKey,
            resolved.TargetNode.NodeKey,
            resolved.Scene,
            resolved.SourceKey,
            resolved.GoalNode,
            resolved.TargetNode,
            semantic,
            explanation,
            resolved.Position,
            resolved.IsActionable));
    }

    private TrackerSummary BuildTrackerSummary(
        Node? requestedNode,
        ViewNode? viewRoot,
        IReadOnlyList<EntityViewNode> frontier,
        IReadOnlyList<ResolvedQuestTarget> targets)
    {
        if (frontier.Count == 0)
            return new TrackerSummary("Ready to turn in", null);

        var summarySemantic = SelectTrackerSemantic(frontier[0], targets)
            ?? ResolvedActionSemanticBuilder.Build(_graph, requestedNode ?? frontier[0].Node, frontier[0], frontier[0]);

        string? prerequisiteQuestName = FindFirstIncompletePrerequisite(viewRoot);

        return NavigationExplanationBuilder.BuildTrackerSummary(
            frontier[0],
            summarySemantic,
            _tracker,
            Math.Max(0, frontier.Count - 1),
            prerequisiteQuestName);
    }

    private string? FindFirstIncompletePrerequisite(ViewNode? viewRoot)
    {
        if (viewRoot == null) return null;
        for (int i = 0; i < viewRoot.Children.Count; i++)
        {
            if (viewRoot.Children[i] is not EntityViewNode child) continue;
            if (child.IsCycleRef) continue;
            if (child.Node.Type != NodeType.Quest) continue;
            if (_gameState.GetState(child.NodeKey) is QuestCompleted) continue;
            // AssignedBy (acceptance gate) or RequiresQuest (prerequisite).
            if (child.EdgeType is EdgeType.AssignedBy or EdgeType.RequiresQuest)
                return child.Node.DisplayName;
        }
        return null;
    }

    private static ResolvedActionSemantic? SelectTrackerSemantic(
        EntityViewNode frontierNode,
        IReadOnlyList<ResolvedQuestTarget> targets)
    {
        for (int i = 0; i < targets.Count; i++)
        {
            if (IsSameGoal(frontierNode, targets[i].GoalNode))
                return targets[i].Semantic;
        }

        return targets.Count > 0 ? targets[0].Semantic : null;
    }

    private static bool IsSameGoal(EntityViewNode frontierNode, EntityViewNode candidateGoal)
    {
        if (frontierNode.EdgeType != candidateGoal.EdgeType)
            return false;

        if (frontierNode.NodeKey == candidateGoal.NodeKey)
            return true;

        return frontierNode.Node.Type == candidateGoal.Node.Type
            && string.Equals(
                frontierNode.Node.DisplayName,
                candidateGoal.Node.DisplayName,
                StringComparison.OrdinalIgnoreCase);
    }

    private readonly struct QuestStructure
    {
        public readonly ViewNode? ViewRoot;
        public readonly IReadOnlyList<EntityViewNode> Frontier;

        public QuestStructure(ViewNode? viewRoot, IReadOnlyList<EntityViewNode> frontier)
        {
            ViewRoot = viewRoot;
            Frontier = frontier;
        }
    }
}
