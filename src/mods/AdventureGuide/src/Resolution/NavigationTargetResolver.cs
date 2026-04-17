using System.Diagnostics;
using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Position;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Resolution;

/// <summary>
/// Resolves navigation targets for compiled-guide node keys.
/// Quest keys use frontier computation; non-quest entity keys (characters,
/// items, mining nodes) resolve positions directly from the compiled guide.
/// </summary>
public sealed class NavigationTargetResolver
{
    private readonly CompiledGuideModel _guide;
        private readonly EffectiveFrontier _frontier;
        private readonly SourceResolver _sourceResolver;
        private readonly ZoneRouter? _zoneRouter;
        private readonly PositionResolverRegistry _positionResolvers;
        private readonly Func<int> _versionProvider;
        private readonly DiagnosticsCore? _diagnostics;
        private readonly Dictionary<string, IReadOnlyList<ResolvedQuestTarget>> _questTargetCache = new(
            StringComparer.Ordinal
        );
        private int _cachedQuestTargetVersion = -1;
        private string? _lastResolvedNodeKey;
        private int _lastResolvedTargetCount;

    public int Version => _versionProvider();

    internal NavigationTargetResolver(
        CompiledGuideModel guide,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver,
        ZoneRouter? zoneRouter,
        PositionResolverRegistry positionResolvers,
        Func<int>? versionProvider = null,
        DiagnosticsCore? diagnostics = null
    )
    {
        _guide = guide;
        _frontier = frontier;
        _sourceResolver = sourceResolver;
        _zoneRouter = zoneRouter;
        _positionResolvers = positionResolvers;
        _versionProvider = versionProvider ?? (() => 0);
        _diagnostics = diagnostics;
    }

    public IReadOnlyList<ResolvedQuestTarget> Resolve(
            string nodeKey,
            string currentScene,
            IResolutionTracer? tracer = null
        )
        {
            var token = _diagnostics?.BeginSpan(
                DiagnosticSpanKind.NavResolverResolve,
                DiagnosticsContext.Root(DiagnosticTrigger.Unknown),
                primaryKey: nodeKey
            );
            long startTick = Stopwatch.GetTimestamp();
            try
            {
                tracer?.OnResolveBegin(nodeKey);

                if (string.IsNullOrWhiteSpace(nodeKey))
                    return Array.Empty<ResolvedQuestTarget>();

                if (!_guide.TryGetNodeId(nodeKey, out int nodeId))
                    return Array.Empty<ResolvedQuestTarget>();

                int version = Version;
                if (_cachedQuestTargetVersion != version)
                {
                    _questTargetCache.Clear();
                    _cachedQuestTargetVersion = version;
                }

                var node = _guide.GetNode(nodeId);
                IReadOnlyList<ResolvedQuestTarget> results;
                if (node.Type == NodeType.Quest)
                {
                    string cacheKey = BuildQuestCacheKey(nodeKey, currentScene);
                    if (!_questTargetCache.TryGetValue(cacheKey, out results!))
                    {
                        int questIndex = _guide.FindQuestIndex(nodeId);
                        if (questIndex < 0)
                        {
                            tracer?.OnResolveEnd(0);
                            return Array.Empty<ResolvedQuestTarget>();
                        }

                        results = ResolveQuestTargets(questIndex, currentScene, tracer);
                        _questTargetCache[cacheKey] = results;
                    }
                }
                else
                {
                    results = ResolveNonQuestEntity(nodeId, nodeKey, node, currentScene);
                }

                _lastResolvedNodeKey = nodeKey;
                _lastResolvedTargetCount = results.Count;
                tracer?.OnResolveEnd(results.Count);
                return results;
            }
            finally
            {
                if (token != null)
                    _diagnostics!.EndSpan(
                        token.Value,
                        Stopwatch.GetTimestamp() - startTick,
                        value0: _lastResolvedTargetCount,
                        value1: 0
                    );
            }
        }

    private IReadOnlyList<ResolvedQuestTarget> ResolveQuestTargets(
            int questIndex,
            string currentScene,
            IResolutionTracer? tracer = null
        )
        {
            var questNode = _guide.GetNode(_guide.QuestNodeId(questIndex));
            tracer?.OnQuestPhase(questIndex, questNode.DbName, "resolving");

            var frontier = new List<FrontierEntry>();
            _frontier.Resolve(questIndex, frontier, -1, tracer);

            var results = new List<ResolvedQuestTarget>();
            var seenTargets = new HashSet<string>(StringComparer.Ordinal);
            var expandedLockedTargets = new HashSet<string>(StringComparer.Ordinal);
            var resolutionSession = new SourceResolver.ResolutionSession();
            for (int i = 0; i < frontier.Count; i++)
            {
                var compiledTargets = CollapseCrossZoneTargets(
                    _sourceResolver.ResolveTargets(frontier[i], currentScene, resolutionSession, tracer),
                    currentScene
                );
                var lockedHopCache = new Dictionary<int, IReadOnlyList<ResolvedTarget>>();
                for (int j = 0; j < compiledTargets.Count; j++)
                    AppendQuestTarget(
                        results,
                        frontier[i],
                        compiledTargets[j],
                        currentScene,
                        new HashSet<int>(),
                        seenTargets,
                        expandedLockedTargets,
                        lockedHopCache,
                        resolutionSession,
                        tracer
                    );
            }

            return results;
        }

    private void AppendQuestTarget(
            List<ResolvedQuestTarget> results,
            FrontierEntry entry,
            ResolvedTarget target,
            string currentScene,
            HashSet<int> lockedHopTrail,
            HashSet<string> seenTargets,
            HashSet<string> expandedLockedTargets,
            Dictionary<int, IReadOnlyList<ResolvedTarget>> lockedHopCache,
            SourceResolver.ResolutionSession resolutionSession,
            IResolutionTracer? tracer = null
        )
        {
            if (
                TryGetLockedHopNodeId(currentScene, target.Scene, out int lockedHopNodeId)
                && lockedHopTrail.Add(lockedHopNodeId)
            )
            {
                try
                {
                    var unlockTargets = GetUnlockTargets(
                        lockedHopNodeId,
                        entry,
                        currentScene,
                        lockedHopCache,
                        resolutionSession,
                        tracer
                    );
                    if (unlockTargets.Count > 0)
                    {
                        for (int i = 0; i < unlockTargets.Count; i++)
                        {
                            string expansionKey = BuildResolvedTargetDedupeKey(entry, unlockTargets[i]);
                            if (!expandedLockedTargets.Add(expansionKey))
                                continue;

                            AppendQuestTarget(
                                results,
                                entry,
                                unlockTargets[i],
                                currentScene,
                                lockedHopTrail,
                                seenTargets,
                                expandedLockedTargets,
                                lockedHopCache,
                                resolutionSession,
                                tracer
                            );
                        }
                        return;
                    }
                }
                finally
                {
                    lockedHopTrail.Remove(lockedHopNodeId);
                }
            }

            TryAddResolvedTarget(results, entry, target, currentScene, seenTargets);
        }

    private IReadOnlyList<ResolvedTarget> GetUnlockTargets(
            int lockedHopNodeId,
            FrontierEntry entry,
            string currentScene,
            Dictionary<int, IReadOnlyList<ResolvedTarget>> lockedHopCache,
            SourceResolver.ResolutionSession resolutionSession,
            IResolutionTracer? tracer
        )
        {
            if (lockedHopCache.TryGetValue(lockedHopNodeId, out var cachedTargets))
                return cachedTargets;

            cachedTargets = CollapseCrossZoneTargets(
                _sourceResolver.ResolveUnlockTargets(
                    lockedHopNodeId,
                    entry,
                    currentScene,
                    resolutionSession,
                    tracer
                ),
                currentScene
            );
            lockedHopCache[lockedHopNodeId] = cachedTargets;
            return cachedTargets;
        }

    private void TryAddResolvedTarget(
            List<ResolvedQuestTarget> results,
            FrontierEntry entry,
            ResolvedTarget target,
            string currentScene,
            HashSet<string> seenTargets
        )
        {
            string dedupeKey = BuildResolvedTargetDedupeKey(entry, target);
            if (!seenTargets.Add(dedupeKey))
                return;

            results.Add(ConvertCompiledTarget(target, currentScene));
        }

    private string BuildResolvedTargetDedupeKey(FrontierEntry entry, ResolvedTarget target)
        {
            string questKey =
                target.RequiredForQuestIndex >= 0
                    ? _guide.GetNodeKey(_guide.QuestNodeId(target.RequiredForQuestIndex))
                    : _guide.GetNodeKey(_guide.QuestNodeId(entry.QuestIndex));
            string goalKey = string.IsNullOrEmpty(target.Semantic.GoalNodeKey)
                ? _guide.GetNodeKey(target.TargetNodeId)
                : target.Semantic.GoalNodeKey;
            return TargetInstanceIdentity.BuildDedupeKey(
                questKey,
                goalKey,
                _guide.GetNodeKey(target.TargetNodeId),
                target.Scene,
                _guide.GetNodeKey(target.PositionNodeId)
            );
        }

    private IReadOnlyList<ResolvedTarget> CollapseCrossZoneTargets(
        IReadOnlyList<ResolvedTarget> targets,
        string currentScene
    )
    {
        if (targets.Count < 2)
            return targets;

        var collapsed = new List<ResolvedTarget>(targets.Count);
        var seenCrossZoneScenes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        for (int i = 0; i < targets.Count; i++)
        {
            var target = targets[i];
            bool sameScene =
                target.Scene == null
                || string.Equals(target.Scene, currentScene, StringComparison.OrdinalIgnoreCase);
            if (sameScene)
            {
                collapsed.Add(target);
                continue;
            }

            bool blocked = TryGetLockedHopNodeId(currentScene, target.Scene, out _);
            string sceneKey = (blocked ? "blocked|" : "direct|") + target.Scene;
            if (seenCrossZoneScenes.Add(sceneKey))
                collapsed.Add(target);
        }

        return collapsed.Count == targets.Count ? targets : collapsed;
    }

    private static string BuildQuestCacheKey(string nodeKey, string currentScene) =>
        nodeKey + "\n" + (currentScene ?? string.Empty).ToUpperInvariant();

    private bool TryGetLockedHopNodeId(
        string currentScene,
        string? targetScene,
        out int lockedHopNodeId
    )
    {
        lockedHopNodeId = -1;
        if (
            _zoneRouter == null
            || string.IsNullOrWhiteSpace(currentScene)
            || string.IsNullOrWhiteSpace(targetScene)
        )
            return false;
        if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
            return false;

        var lockedHop = _zoneRouter.FindFirstLockedHop(currentScene, targetScene);
        return lockedHop != null && _guide.TryGetNodeId(lockedHop.ZoneLineKey, out lockedHopNodeId);
    }

    internal NavigationDiagnosticsSnapshot ExportDiagnosticsSnapshot()
    {
        return new NavigationDiagnosticsSnapshot(
            lastForceReason: DiagnosticTrigger.Unknown,
            cacheEntryCount: 0,
            currentTargetKey: _lastResolvedNodeKey,
            lastResolvedTargetCount: _lastResolvedTargetCount
        );
    }

    private ResolvedQuestTarget ConvertCompiledTarget(ResolvedTarget target, string currentScene)
    {
        string targetNodeKey = _guide.GetNodeKey(target.TargetNodeId);
        string sourceKey = _guide.GetNodeKey(target.PositionNodeId);
        var goalNode = BuildGoalContext(target);
        var targetNode = BuildNodeContext(target.TargetNodeId);
        var explanation =
            target.Semantic.ActionKind == ResolvedActionKind.LootChest
                ? NavigationExplanationBuilder.BuildLootChestExplanation(
                    target.Semantic,
                    goalNode,
                    targetNode
                )
                : NavigationExplanationBuilder.Build(target.Semantic, goalNode, targetNode);

        string? requiredForQuestKey = null;
        if (target.RequiredForQuestIndex >= 0)
            requiredForQuestKey = _guide.GetNodeKey(
                _guide.QuestNodeId(target.RequiredForQuestIndex)
            );

        return new ResolvedQuestTarget(
            targetNodeKey,
            target.Scene,
            sourceKey,
            goalNode,
            targetNode,
            target.Semantic,
            explanation,
            target.X,
            target.Y,
            target.Z,
            target.IsActionable,
            requiredForQuestKey: requiredForQuestKey,
            isBlockedPath: IsSceneBlocked(currentScene, target.Scene)
        );
    }

    private ResolvedNodeContext BuildGoalContext(ResolvedTarget target)
    {
        if (!string.IsNullOrEmpty(target.Semantic.GoalNodeKey))
            return BuildNodeContext(target.Semantic.GoalNodeKey);

        return BuildNodeContext(target.TargetNodeId);
    }

    private ResolvedNodeContext BuildNodeContext(int nodeId) =>
        BuildNodeContext(_guide.GetNodeKey(nodeId));

    private ResolvedNodeContext BuildNodeContext(string nodeKey)
    {
        var node = _guide.GetNode(nodeKey) ?? BuildNodeFromGuide(nodeKey);
        return new ResolvedNodeContext(nodeKey, node);
    }

    private Node BuildNodeFromGuide(string nodeKey)
    {
        if (!_guide.TryGetNodeId(nodeKey, out int nodeId))
        {
            return new Node
            {
                Key = nodeKey,
                Type = NodeType.WorldObject,
                DisplayName = nodeKey,
            };
        }

        var record = _guide.GetNode(nodeId);
        return new Node
        {
            Key = nodeKey,
            Type = record.Type,
            DisplayName = _guide.GetDisplayName(nodeId),
            Scene = _guide.GetScene(nodeId),
            X = record.X,
            Y = record.Y,
            Z = record.Z,
            DbName = record.DbName,
            Repeatable = record.Repeatable,
            Implicit = record.Implicit,
            Disabled = record.Disabled,
            IsEnabled = record.IsEnabled,
        };
    }

    // ---------------------------------------------------------------
    // Non-quest entity resolution
    // ---------------------------------------------------------------

    private IReadOnlyList<ResolvedQuestTarget> ResolveNonQuestEntity(
        int nodeId,
        string nodeKey,
        Node node,
        string currentScene
    )
    {
        return node.Type switch
        {
            NodeType.Character => ResolveCharacterTargets(nodeKey, node, currentScene),
            NodeType.Item => ResolveItemTargets(nodeId, nodeKey, node, currentScene),
            NodeType.MiningNode
            or NodeType.ItemBag when node.X.HasValue && node.Y.HasValue && node.Z.HasValue =>
                ResolveMutablePositionedEntityTargets(nodeKey, node, currentScene),
            _ when node.X.HasValue && node.Y.HasValue && node.Z.HasValue =>
                ResolvePositionedEntityTargets(nodeKey, node, currentScene),
            _ => Array.Empty<ResolvedQuestTarget>(),
        };
    }

    private ResolvedActionKind ResolveCharacterActionKind(string nodeKey)
    {
        if (_guide.OutEdges(nodeKey, EdgeType.DropsItem).Count > 0)
            return ResolvedActionKind.Kill;
        if (_guide.OutEdges(nodeKey, EdgeType.SellsItem).Count > 0)
            return ResolvedActionKind.Buy;
        return ResolvedActionKind.Talk;
    }

    private IReadOnlyList<ResolvedQuestTarget> ResolveCharacterTargets(
        string nodeKey,
        Node node,
        string currentScene
    )
    {
        var spawnEdges = _guide.OutEdges(nodeKey, EdgeType.HasSpawn);
        if (spawnEdges.Count == 0)
            return Array.Empty<ResolvedQuestTarget>();

        var nodeContext = BuildNodeContext(nodeKey);
        var results = new List<ResolvedQuestTarget>();
        var actionKind = ResolveCharacterActionKind(nodeKey);
        var targetKind =
            actionKind == ResolvedActionKind.Kill
                ? NavigationTargetKind.Enemy
                : NavigationTargetKind.Character;

        for (int i = 0; i < spawnEdges.Count; i++)
        {
            string spawnKey = spawnEdges[i].Target;
            var spawnNode = _guide.GetNode(spawnKey);
            if (
                spawnNode == null
                || !spawnNode.X.HasValue
                || !spawnNode.Y.HasValue
                || !spawnNode.Z.HasValue
            )
                continue;

            var semantic = BuildDirectNavigationSemantic(
                node,
                targetKind,
                actionKind,
                _guide.GetZoneDisplay(spawnNode.Scene)
            );
            var explanation = NavigationExplanationBuilder.Build(
                semantic,
                nodeContext,
                nodeContext
            );

            results.Add(
                new ResolvedQuestTarget(
                    nodeKey,
                    spawnNode.Scene,
                    spawnKey,
                    nodeContext,
                    nodeContext,
                    semantic,
                    explanation,
                    spawnNode.X.Value,
                    spawnNode.Y.Value,
                    spawnNode.Z.Value,
                    isActionable: true,
                    isBlockedPath: IsSceneBlocked(currentScene, spawnNode.Scene)
                )
            );
        }

        return results;
    }

    private IReadOnlyList<ResolvedQuestTarget> ResolveItemTargets(
        int nodeId,
        string nodeKey,
        Node node,
        string currentScene
    )
    {
        int itemIndex = _guide.FindItemIndex(nodeId);
        if (itemIndex < 0)
            return Array.Empty<ResolvedQuestTarget>();

        var sources = _guide.GetItemSources(itemIndex);
        if (sources.Length == 0)
            return Array.Empty<ResolvedQuestTarget>();

        var nodeContext = BuildNodeContext(nodeKey);
        var results = new List<ResolvedQuestTarget>();

        for (int i = 0; i < sources.Length; i++)
        {
            var source = sources[i];
            string sourceKey = _guide.GetNodeKey(source.SourceId);
            var sourceNode = _guide.GetNode(source.SourceId);
            string? sourceScene = _guide.GetSourceScene(source);
            var sourceContext = BuildNodeContext(sourceKey);
            var semantic = BuildDirectNavigationSemantic(
                node,
                NavigationTargetKind.Item,
                ResolvedActionKind.Collect,
                _guide.GetZoneDisplay(sourceScene)
            );
            var explanation = NavigationExplanationBuilder.Build(
                semantic,
                nodeContext,
                sourceContext
            );

            if (sourceNode.Type is NodeType.MiningNode or NodeType.ItemBag)
            {
                var positions = new List<ResolvedPosition>();
                _positionResolvers.Resolve(sourceKey, positions);
                for (int j = 0; j < positions.Count; j++)
                {
                    var position = positions[j];
                    results.Add(
                        new ResolvedQuestTarget(
                            sourceKey,
                            position.Scene,
                            position.SourceKey ?? sourceKey,
                            nodeContext,
                            sourceContext,
                            semantic,
                            explanation,
                            position.X,
                            position.Y,
                            position.Z,
                            isActionable: position.IsActionable,
                            isBlockedPath: IsSceneBlocked(currentScene, position.Scene)
                        )
                    );
                }
                continue;
            }

            // Use source's spawn positions if available, otherwise the source node's own coords.
            if (source.Positions.Length > 0)
            {
                for (int j = 0; j < source.Positions.Length; j++)
                {
                    var pos = source.Positions[j];
                    results.Add(
                        new ResolvedQuestTarget(
                            sourceKey,
                            sourceScene,
                            sourceKey,
                            nodeContext,
                            sourceContext,
                            semantic,
                            explanation,
                            pos.X,
                            pos.Y,
                            pos.Z,
                            isActionable: true,
                            isBlockedPath: IsSceneBlocked(currentScene, sourceScene)
                        )
                    );
                }
            }
            else if (sourceNode.X.HasValue && sourceNode.Y.HasValue && sourceNode.Z.HasValue)
            {
                results.Add(
                    new ResolvedQuestTarget(
                        sourceKey,
                        sourceScene,
                        sourceKey,
                        nodeContext,
                        sourceContext,
                        semantic,
                        explanation,
                        sourceNode.X.Value,
                        sourceNode.Y.Value,
                        sourceNode.Z.Value,
                        isActionable: true,
                        isBlockedPath: IsSceneBlocked(currentScene, sourceScene)
                    )
                );
            }
        }

        return results;
    }

    private IReadOnlyList<ResolvedQuestTarget> ResolveMutablePositionedEntityTargets(
        string nodeKey,
        Node node,
        string currentScene
    )
    {
        var positions = new List<ResolvedPosition>();
        _positionResolvers.Resolve(nodeKey, positions);
        if (positions.Count == 0)
            return Array.Empty<ResolvedQuestTarget>();

        var nodeContext = BuildNodeContext(nodeKey);
        var actionKind =
            node.Type == NodeType.MiningNode ? ResolvedActionKind.Mine : ResolvedActionKind.Collect;
        var semantic = BuildDirectNavigationSemantic(
            node,
            NavigationTargetKind.Object,
            actionKind,
            _guide.GetZoneDisplay(node.Scene)
        );
        var explanation = NavigationExplanationBuilder.Build(semantic, nodeContext, nodeContext);
        var results = new List<ResolvedQuestTarget>(positions.Count);
        for (int i = 0; i < positions.Count; i++)
        {
            var position = positions[i];
            results.Add(
                new ResolvedQuestTarget(
                    nodeKey,
                    position.Scene,
                    position.SourceKey ?? nodeKey,
                    nodeContext,
                    nodeContext,
                    semantic,
                    explanation,
                    position.X,
                    position.Y,
                    position.Z,
                    isActionable: position.IsActionable,
                    isBlockedPath: IsSceneBlocked(currentScene, position.Scene)
                )
            );
        }
        return results;
    }

    private IReadOnlyList<ResolvedQuestTarget> ResolvePositionedEntityTargets(
        string nodeKey,
        Node node,
        string currentScene
    )
    {
        var nodeContext = BuildNodeContext(nodeKey);
        var actionKind =
            node.Type == NodeType.MiningNode ? ResolvedActionKind.Mine
            : node.Type == NodeType.Water ? ResolvedActionKind.Fish
            : ResolvedActionKind.Collect;
        var targetKind =
            node.Type == NodeType.Character
                ? NavigationTargetKind.Character
                : NavigationTargetKind.Object;
        var semantic = BuildDirectNavigationSemantic(
            node,
            targetKind,
            actionKind,
            _guide.GetZoneDisplay(node.Scene)
        );
        var explanation = NavigationExplanationBuilder.Build(semantic, nodeContext, nodeContext);

        return new[]
        {
            new ResolvedQuestTarget(
                nodeKey,
                node.Scene,
                nodeKey,
                nodeContext,
                nodeContext,
                semantic,
                explanation,
                node.X!.Value,
                node.Y!.Value,
                node.Z!.Value,
                isActionable: true,
                isBlockedPath: IsSceneBlocked(currentScene, node.Scene)
            ),
        };
    }

    private bool IsSceneBlocked(string currentScene, string? targetScene)
    {
        if (_zoneRouter == null)
            return false;
        if (string.IsNullOrWhiteSpace(currentScene) || string.IsNullOrWhiteSpace(targetScene))
            return false;
        if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
            return false;
        return _zoneRouter.FindFirstLockedHop(currentScene, targetScene) != null;
    }

    private static ResolvedActionSemantic BuildDirectNavigationSemantic(
        Node targetNode,
        NavigationTargetKind targetKind,
        ResolvedActionKind actionKind,
        string? zoneText
    )
    {
        return new ResolvedActionSemantic(
            NavigationGoalKind.Generic,
            targetKind,
            actionKind,
            goalNodeKey: null,
            goalQuantity: null,
            keywordText: null,
            payloadText: null,
            targetIdentityText: targetNode.DisplayName,
            contextText: null,
            rationaleText: null,
            zoneText: zoneText,
            availabilityText: null,
            preferredMarkerKind: QuestMarkerKind.Objective,
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(
                QuestMarkerKind.Objective
            )
        );
    }
}
