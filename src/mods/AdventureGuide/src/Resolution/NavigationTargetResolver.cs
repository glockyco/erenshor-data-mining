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
    private readonly Func<int> _versionProvider;

    public int Version => _versionProvider();

    public NavigationTargetResolver(
        CompiledGuideModel guide,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver,
        ZoneRouter? zoneRouter,
        Func<int>? versionProvider = null)
    {
        _guide = guide;
        _frontier = frontier;
        _sourceResolver = sourceResolver;
        _zoneRouter = zoneRouter;
        _versionProvider = versionProvider ?? (() => 0);
    }

    public IReadOnlyList<ResolvedQuestTarget> Resolve(string nodeKey, string currentScene, IResolutionTracer? tracer = null)
    {
        tracer?.OnResolveBegin(nodeKey);

        if (string.IsNullOrWhiteSpace(nodeKey))
            return Array.Empty<ResolvedQuestTarget>();

        if (!_guide.TryGetNodeId(nodeKey, out int nodeId))
            return Array.Empty<ResolvedQuestTarget>();

        var node = _guide.GetNode(nodeId);
        IReadOnlyList<ResolvedQuestTarget> results;
        if (node.Type == NodeType.Quest)
        {
            int questIndex = _guide.FindQuestIndex(nodeId);
            if (questIndex < 0)
            {
                tracer?.OnResolveEnd(0);
                return Array.Empty<ResolvedQuestTarget>();
            }

            results = ResolveQuestTargets(questIndex, currentScene, tracer);
        }
        else
        {
            results = ResolveNonQuestEntity(nodeId, nodeKey, node, currentScene);
        }

        tracer?.OnResolveEnd(results.Count);
        return results;
    }

    private IReadOnlyList<ResolvedQuestTarget> ResolveQuestTargets(int questIndex, string currentScene, IResolutionTracer? tracer = null)
    {
        var questNode = _guide.GetNode(_guide.QuestNodeId(questIndex));
        tracer?.OnQuestPhase(questIndex, questNode.DbName, "resolving");

        var frontier = new List<FrontierEntry>();
        _frontier.Resolve(questIndex, frontier, -1, tracer);

        var results = new List<ResolvedQuestTarget>();
        for (int i = 0; i < frontier.Count; i++)
        {
            var compiledTargets = _sourceResolver.ResolveTargets(frontier[i], currentScene, tracer);
            for (int j = 0; j < compiledTargets.Count; j++)
                AppendQuestTarget(results, frontier[i], compiledTargets[j], currentScene, new HashSet<int>(), tracer);
        }

        return results;
    }

    private void AppendQuestTarget(
        List<ResolvedQuestTarget> results,
        FrontierEntry entry,
        ResolvedTarget target,
        string currentScene,
        HashSet<int> lockedHopTrail,
        IResolutionTracer? tracer = null)
    {
        if (TryGetLockedHopNodeId(currentScene, target.Scene, out int lockedHopNodeId)
            && lockedHopTrail.Add(lockedHopNodeId))
        {
            try
            {
                var unlockTargets = _sourceResolver.ResolveUnlockTargets(lockedHopNodeId, entry, currentScene, tracer);
                if (unlockTargets.Count > 0)
                {
                    for (int i = 0; i < unlockTargets.Count; i++)
                        AppendQuestTarget(results, entry, unlockTargets[i], currentScene, lockedHopTrail, tracer);
                    return;
                }
            }
            finally
            {
                lockedHopTrail.Remove(lockedHopNodeId);
            }
        }

        results.Add(ConvertCompiledTarget(target, currentScene));
    }

    private bool TryGetLockedHopNodeId(string currentScene, string? targetScene, out int lockedHopNodeId)
    {
        lockedHopNodeId = -1;
        if (_zoneRouter == null || string.IsNullOrWhiteSpace(currentScene) || string.IsNullOrWhiteSpace(targetScene))
            return false;
        if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
            return false;

        var lockedHop = _zoneRouter.FindFirstLockedHop(currentScene, targetScene);
        return lockedHop != null && _guide.TryGetNodeId(lockedHop.ZoneLineKey, out lockedHopNodeId);
    }


    private ResolvedQuestTarget ConvertCompiledTarget(ResolvedTarget target, string currentScene)
    {
        string targetNodeKey = _guide.GetNodeKey(target.TargetNodeId);
        string sourceKey = _guide.GetNodeKey(target.PositionNodeId);
        var goalNode = BuildGoalContext(target);
        var targetNode = BuildNodeContext(target.TargetNodeId);
        var explanation = target.Semantic.ActionKind == ResolvedActionKind.LootChest
            ? NavigationExplanationBuilder.BuildLootChestExplanation(target.Semantic, goalNode, targetNode)
            : NavigationExplanationBuilder.Build(target.Semantic, goalNode, targetNode);

        string? requiredForQuestKey = null;
        if (target.RequiredForQuestIndex >= 0)
            requiredForQuestKey = _guide.GetNodeKey(_guide.QuestNodeId(target.RequiredForQuestIndex));

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
            isBlockedPath: IsSceneBlocked(currentScene, target.Scene));
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

    private IReadOnlyList<ResolvedQuestTarget> ResolveNonQuestEntity(int nodeId, string nodeKey, Node node, string currentScene)
    {
        return node.Type switch
        {
            NodeType.Character => ResolveCharacterTargets(nodeKey, node, currentScene),
            NodeType.Item => ResolveItemTargets(nodeId, nodeKey, node, currentScene),
            _ when node.X.HasValue && node.Y.HasValue && node.Z.HasValue
                => ResolvePositionedEntityTargets(nodeKey, node, currentScene),
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

    private IReadOnlyList<ResolvedQuestTarget> ResolveCharacterTargets(string nodeKey, Node node, string currentScene)
    {
        var spawnEdges = _guide.OutEdges(nodeKey, EdgeType.HasSpawn);
        if (spawnEdges.Count == 0)
            return Array.Empty<ResolvedQuestTarget>();

        var nodeContext = BuildNodeContext(nodeKey);
        var results = new List<ResolvedQuestTarget>();
        var actionKind = ResolveCharacterActionKind(nodeKey);
        var targetKind = actionKind == ResolvedActionKind.Kill
            ? NavigationTargetKind.Enemy
            : NavigationTargetKind.Character;

        for (int i = 0; i < spawnEdges.Count; i++)
        {
            string spawnKey = spawnEdges[i].Target;
            var spawnNode = _guide.GetNode(spawnKey);
            if (spawnNode == null || !spawnNode.X.HasValue || !spawnNode.Y.HasValue || !spawnNode.Z.HasValue)
                continue;

            var semantic = BuildDirectNavigationSemantic(
                node, targetKind, actionKind, _guide.GetZoneDisplay(spawnNode.Scene));
            var explanation = NavigationExplanationBuilder.Build(semantic, nodeContext, nodeContext);

            results.Add(new ResolvedQuestTarget(
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
                isBlockedPath: IsSceneBlocked(currentScene, spawnNode.Scene)));
        }

        return results;
    }

    private IReadOnlyList<ResolvedQuestTarget> ResolveItemTargets(int nodeId, string nodeKey, Node node, string currentScene)
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

            // Use source's spawn positions if available, otherwise the source node's own coords.
            if (source.Positions.Length > 0)
            {
                for (int j = 0; j < source.Positions.Length; j++)
                {
                    var pos = source.Positions[j];
                    var sourceContext = BuildNodeContext(sourceKey);
                    var semantic = BuildDirectNavigationSemantic(
                        node, NavigationTargetKind.Item, ResolvedActionKind.Collect, _guide.GetZoneDisplay(sourceScene));
                    var explanation = NavigationExplanationBuilder.Build(semantic, nodeContext, sourceContext);

                    results.Add(new ResolvedQuestTarget(
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
                        isBlockedPath: IsSceneBlocked(currentScene, sourceScene)));
                }
            }
            else if (sourceNode.X.HasValue && sourceNode.Y.HasValue && sourceNode.Z.HasValue)
            {
                var sourceContext = BuildNodeContext(sourceKey);
                var semantic = BuildDirectNavigationSemantic(
                    node, NavigationTargetKind.Item, ResolvedActionKind.Collect, _guide.GetZoneDisplay(sourceScene));
                var explanation = NavigationExplanationBuilder.Build(semantic, nodeContext, sourceContext);

                results.Add(new ResolvedQuestTarget(
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
                    isBlockedPath: IsSceneBlocked(currentScene, sourceScene)));
            }
        }

        return results;
    }

    private IReadOnlyList<ResolvedQuestTarget> ResolvePositionedEntityTargets(string nodeKey, Node node, string currentScene)
    {
        var nodeContext = BuildNodeContext(nodeKey);
        var actionKind = node.Type == NodeType.MiningNode ? ResolvedActionKind.Mine
            : node.Type == NodeType.Water ? ResolvedActionKind.Fish
            : ResolvedActionKind.Collect;
        var targetKind = node.Type == NodeType.Character ? NavigationTargetKind.Character
            : NavigationTargetKind.Object;
        var semantic = BuildDirectNavigationSemantic(node, targetKind, actionKind, _guide.GetZoneDisplay(node.Scene));
        var explanation = NavigationExplanationBuilder.Build(semantic, nodeContext, nodeContext);

        return new[] { new ResolvedQuestTarget(
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
            isBlockedPath: IsSceneBlocked(currentScene, node.Scene)) };
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
        Node targetNode, NavigationTargetKind targetKind, ResolvedActionKind actionKind, string? zoneText)
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
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(QuestMarkerKind.Objective));
    }
}
