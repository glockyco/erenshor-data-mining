using AdventureGuide.CompiledGuide;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Position;

namespace AdventureGuide.Resolution;

public enum ResolvedTargetRole
{
    Giver,
    Objective,
    TurnIn,
}

public readonly struct ResolvedTarget
{
    public ResolvedTarget(
        int targetNodeId,
        int positionNodeId,
        ResolvedTargetRole role,
        ResolvedActionSemantic semantic,
        float x,
        float y,
        float z,
        string? scene,
        bool isLive,
        bool isActionable,
        int questIndex,
        int requiredForQuestIndex
    )
    {
        TargetNodeId = targetNodeId;
        PositionNodeId = positionNodeId;
        Role = role;
        Semantic = semantic;
        X = x;
        Y = y;
        Z = z;
        Scene = scene;
        IsLive = isLive;
        IsActionable = isActionable;
        QuestIndex = questIndex;
        RequiredForQuestIndex = requiredForQuestIndex;
    }

    public int TargetNodeId { get; }
    public int PositionNodeId { get; }
    public ResolvedTargetRole Role { get; }
    public ResolvedActionSemantic Semantic { get; }
    public float X { get; }
    public float Y { get; }
    public float Z { get; }
    public string? Scene { get; }
    public bool IsLive { get; }
    public bool IsActionable { get; }
    public int QuestIndex { get; }
    public int RequiredForQuestIndex { get; }
}

public sealed class SourceResolver
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;
    private readonly UnlockPredicateEvaluator _unlocks;
    private readonly ILivePositionProvider _livePositions;
    private readonly PositionResolverRegistry _positionResolvers;

    private const byte EdgeDropsItem = (byte)EdgeType.DropsItem;
    private const byte EdgeSellsItem = (byte)EdgeType.SellsItem;
    private const byte EdgeGivesItem = (byte)EdgeType.GivesItem;
    private const byte EdgeYieldsItem = (byte)EdgeType.YieldsItem;
    private const byte EdgeContains = (byte)EdgeType.Contains;
    private const byte EdgeProduces = (byte)EdgeType.Produces;

    public SourceResolver(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        UnlockPredicateEvaluator unlocks,
        ILivePositionProvider livePositions,
        PositionResolverRegistry positionResolvers
    )
    {
        _guide = guide;
        _phases = phases;
        _unlocks = unlocks;
        _livePositions = livePositions;
        _positionResolvers = positionResolvers;
    }

    internal sealed class ResolutionSession
    {
        public readonly Dictionary<(int QuestIndex, int RequiredForQuestIndex), IReadOnlyList<ResolvedTarget>> QuestFrontierCache = new();
        public readonly HashSet<(int QuestIndex, int RequiredForQuestIndex)> ActiveQuestFrontiers = new();
        public readonly Dictionary<
            (int QuestIndex, byte Phase, int RequiredForQuestIndex, int ItemNodeId, byte SemanticKind, int GiverNodeId),
            IReadOnlyList<ResolvedTarget>
        > ItemRequirementCache = new();
        public readonly HashSet<
            (int QuestIndex, byte Phase, int RequiredForQuestIndex, int ItemNodeId, byte SemanticKind, int GiverNodeId)
        > ActiveItemRequirements = new();
        public readonly Dictionary<
            (int QuestIndex, byte Phase, int RequiredForQuestIndex, int TargetNodeId),
            IReadOnlyList<ResolvedTarget>
        > UnlockRequirementCache = new();
        public readonly HashSet<
            (int QuestIndex, byte Phase, int RequiredForQuestIndex, int TargetNodeId)
        > ActiveUnlockRequirements = new();
        public readonly Dictionary<
            (int QuestIndex, byte Phase, int RequiredForQuestIndex, int RecipeNodeId),
            IReadOnlyList<ResolvedTarget>
        > RecipeMaterialCache = new();
        public readonly HashSet<
            (int QuestIndex, byte Phase, int RequiredForQuestIndex, int RecipeNodeId)
        > ActiveRecipeMaterials = new();
    }

    private enum ItemRequirementSemanticKind : byte
    {
        Objective = 0,
        Giver = 1,
    }

    private static IReadOnlyList<ResolvedTarget> FreezeResults(List<ResolvedTarget> results) =>
        results.Count == 0 ? Array.Empty<ResolvedTarget>() : results;

    private static IReadOnlyList<ResolvedTarget> ResolveCached<TKey>(
        Dictionary<TKey, IReadOnlyList<ResolvedTarget>> cache,
        HashSet<TKey> active,
        TKey key,
        Func<IReadOnlyList<ResolvedTarget>> build
    )
        where TKey : notnull
    {
        if (cache.TryGetValue(key, out var cached))
            return cached;
        if (!active.Add(key))
            return Array.Empty<ResolvedTarget>();

        try
        {
            cached = build();
            cache[key] = cached;
            return cached;
        }
        finally
        {
            active.Remove(key);
        }
    }

    public IReadOnlyList<ResolvedTarget> ResolveTargets(
            FrontierEntry entry,
            string currentScene,
            IResolutionTracer? tracer = null
        )
        {
            return ResolveTargets(entry, currentScene, new ResolutionSession(), tracer);
        }

    public IReadOnlyList<ResolvedTarget> ResolveUnlockTargets(
            int targetNodeId,
            FrontierEntry entry,
            string currentScene,
            IResolutionTracer? tracer = null
        )
        {
            return ResolveUnlockTargets(targetNodeId, entry, currentScene, new ResolutionSession(), tracer);
        }

    internal IReadOnlyList<ResolvedTarget> ResolveTargets(
        FrontierEntry entry,
        string currentScene,
        ResolutionSession session,
        IResolutionTracer? tracer = null
    )
    {
        var results = new List<ResolvedTarget>();
        ResolveEntry(
            entry,
            currentScene,
            results,
            session,
            new HashSet<int>(),
            new HashSet<int>(),
            tracer
        );
        return results;
    }

    internal IReadOnlyList<ResolvedTarget> ResolveUnlockTargets(
        int targetNodeId,
        FrontierEntry entry,
        string currentScene,
        ResolutionSession session,
        IResolutionTracer? tracer = null
    )
    {
        var results = ResolveBlockingUnlockRequirements(
            targetNodeId,
            entry,
            currentScene,
            session,
            new HashSet<int>(),
            new HashSet<int>(),
            tracer
        );
        return results ?? Array.Empty<ResolvedTarget>();
    }

    private void ResolveEntry(
            FrontierEntry entry,
            string currentScene,
            List<ResolvedTarget> results,
            ResolutionSession session,
            HashSet<int> questTrail,
            HashSet<int> itemTrail,
            IResolutionTracer? tracer = null
        )
        {
            if (!questTrail.Add(entry.QuestIndex))
                return;

            try
            {
                switch (entry.Phase)
                {
                    case QuestPhase.ReadyToAccept:
                        foreach (int giverId in _guide.GiverIds(entry.QuestIndex))
                        {
                            var giverNode = _guide.GetNode(giverId);
                            if (giverNode.Type is NodeType.Item or NodeType.Book)
                            {
                                results.AddRange(
                                    ResolveItemRequirement(
                                        giverId,
                                        entry,
                                        currentScene,
                                        session,
                                        questTrail,
                                        itemTrail,
                                        ItemRequirementSemanticKind.Giver,
                                        giverId,
                                        tracer
                                    )
                                );
                                continue;
                            }

                            int giverQuestIndex = _guide.FindQuestIndex(giverId);
                            if (
                                giverNode.Type == NodeType.Quest
                                && giverQuestIndex >= 0
                                && !_phases.IsCompleted(giverQuestIndex)
                            )
                            {
                                results.AddRange(
                                    ResolveQuestFrontier(
                                        giverQuestIndex,
                                        entry.QuestIndex,
                                        currentScene,
                                        session,
                                        questTrail,
                                        itemTrail,
                                        tracer
                                    )
                                );
                                continue;
                            }

                            EmitNodePosition(
                                giverId,
                                giverId,
                                ResolvedTargetRole.Giver,
                                BuildGiverSemantic(entry.QuestIndex, giverId),
                                entry,
                                results,
                                tracer
                            );
                        }
                        break;

                    case QuestPhase.Accepted:
                        bool emittedObjective = false;
                        foreach (var requirement in _guide.RequiredItems(entry.QuestIndex))
                        {
                            int itemIndex = _guide.FindItemIndex(requirement.ItemId);
                            if (
                                itemIndex >= 0
                                && _phases.GetItemCount(itemIndex) >= requirement.Quantity
                            )
                                continue;

                            emittedObjective = true;
                            results.AddRange(
                                ResolveItemRequirement(
                                    requirement.ItemId,
                                    entry,
                                    currentScene,
                                    session,
                                    questTrail,
                                    itemTrail,
                                    ItemRequirementSemanticKind.Objective,
                                    giverNodeId: -1,
                                    tracer
                                )
                            );
                        }

                        foreach (var step in _guide.Steps(entry.QuestIndex))
                        {
                            emittedObjective = true;
                            EmitNodePosition(
                                step.TargetId,
                                step.TargetId,
                                ResolvedTargetRole.Objective,
                                BuildStepSemantic(step),
                                entry,
                                results,
                                tracer
                            );
                        }

                        if (!emittedObjective)
                        {
                            foreach (int completerId in _guide.CompleterIds(entry.QuestIndex))
                            {
                                EmitNodePosition(
                                    completerId,
                                    completerId,
                                    ResolvedTargetRole.TurnIn,
                                    BuildTurnInSemantic(entry.QuestIndex, completerId),
                                    entry,
                                    results,
                                    tracer
                                );
                            }
                        }
                        break;
                }
            }
            finally
            {
                questTrail.Remove(entry.QuestIndex);
            }
        }

    private IReadOnlyList<ResolvedTarget> ResolveQuestFrontier(
            int questIndex,
            int requiredForQuestIndex,
            string currentScene,
            ResolutionSession session,
            HashSet<int> questTrail,
            HashSet<int> itemTrail,
            IResolutionTracer? tracer = null
        )
        {
            return ResolveCached(
                session.QuestFrontierCache,
                session.ActiveQuestFrontiers,
                (questIndex, requiredForQuestIndex),
                () =>
                {
                    var frontier = new List<FrontierEntry>();
                    new EffectiveFrontier(_guide, _phases).Resolve(
                        questIndex,
                        frontier,
                        requiredForQuestIndex,
                        tracer
                    );
                    var results = new List<ResolvedTarget>();
                    for (int i = 0; i < frontier.Count; i++)
                        ResolveEntry(frontier[i], currentScene, results, session, questTrail, itemTrail, tracer);
                    return FreezeResults(results);
                }
            );
        }

    private IReadOnlyList<ResolvedTarget> ResolveItemRequirement(
            int itemNodeId,
            FrontierEntry entry,
            string currentScene,
            ResolutionSession session,
            HashSet<int> questTrail,
            HashSet<int> itemTrail,
            ItemRequirementSemanticKind semanticKind,
            int giverNodeId,
            IResolutionTracer? tracer = null
        )
        {
            return ResolveCached(
                session.ItemRequirementCache,
                session.ActiveItemRequirements,
                (
                    entry.QuestIndex,
                    (byte)entry.Phase,
                    entry.RequiredForQuestIndex,
                    itemNodeId,
                    (byte)semanticKind,
                    giverNodeId
                ),
                () =>
                {
                    if (!itemTrail.Add(itemNodeId))
                        return Array.Empty<ResolvedTarget>();

                    try
                    {
                        var results = new List<ResolvedTarget>();
                        int itemIndex = _guide.FindItemIndex(itemNodeId);
                        if (itemIndex >= 0)
                        {
                            foreach (var source in GetVisibleItemSources(itemIndex, tracer))
                            {
                                var semantic = semanticKind == ItemRequirementSemanticKind.Giver
                                    ? BuildGiverSemantic(entry.QuestIndex, giverNodeId)
                                    : BuildSourceSemantic(itemNodeId, source);
                                ResolveItemSource(
                                    itemNodeId,
                                    source,
                                    semantic,
                                    entry,
                                    currentScene,
                                    results,
                                    session,
                                    questTrail,
                                    itemTrail,
                                    tracer
                                );
                            }
                        }

                        foreach (
                            var rewardEdge in _guide.InEdges(
                                _guide.GetNodeKey(itemNodeId),
                                EdgeType.RewardsItem
                            )
                        )
                        {
                            if (!_guide.TryGetNodeId(rewardEdge.Source, out int rewardQuestId))
                                continue;

                            int rewardQuestIndex = _guide.FindQuestIndex(rewardQuestId);
                            if (rewardQuestIndex < 0 || _phases.IsCompleted(rewardQuestIndex))
                                continue;

                            results.AddRange(
                                ResolveQuestFrontier(
                                    rewardQuestIndex,
                                    entry.QuestIndex,
                                    currentScene,
                                    session,
                                    questTrail,
                                    itemTrail,
                                    tracer
                                )
                            );
                        }

                        return FreezeResults(results);
                    }
                    finally
                    {
                        itemTrail.Remove(itemNodeId);
                    }
                }
            );
        }

    private void ResolveItemSource(
            int itemNodeId,
            SourceSiteEntry source,
            ResolvedActionSemantic semantic,
            FrontierEntry entry,
            string currentScene,
            List<ResolvedTarget> results,
            ResolutionSession session,
            HashSet<int> questTrail,
            HashSet<int> itemTrail,
            IResolutionTracer? tracer = null
        )
        {
            var sourceNode = _guide.GetNode(source.SourceId);
            if (sourceNode.Type == NodeType.Recipe && source.EdgeType == EdgeProduces)
            {
                results.AddRange(
                    ResolveRecipeMaterials(
                        source.SourceId,
                        entry,
                        currentScene,
                        session,
                        questTrail,
                        itemTrail,
                        tracer
                    )
                );
                return;
            }

            var unlockTargets = ResolveBlockingUnlockRequirements(
                source.SourceId,
                entry,
                currentScene,
                session,
                questTrail,
                itemTrail,
                tracer
            );
            if (unlockTargets != null)
            {
                results.AddRange(unlockTargets);
                return;
            }

            var role =
                semantic.GoalKind == NavigationGoalKind.StartQuest
                    ? ResolvedTargetRole.Giver
                    : ResolvedTargetRole.Objective;
            EmitSourceTargets(source, role, semantic, entry, results, tracer);
        }

    private void ResolveUnlockCondition(
            UnlockConditionEntry condition,
            FrontierEntry entry,
            string currentScene,
            List<ResolvedTarget> results,
            ResolutionSession session,
            HashSet<int> questTrail,
            HashSet<int> itemTrail,
            IResolutionTracer? tracer = null
        )
        {
            if (condition.CheckType == 0)
            {
                int questIndex = _guide.FindQuestIndex(condition.SourceId);
                if (questIndex >= 0 && !_phases.IsCompleted(questIndex))
                    results.AddRange(
                        ResolveQuestFrontier(
                            questIndex,
                            entry.QuestIndex,
                            currentScene,
                            session,
                            questTrail,
                            itemTrail,
                            tracer
                        )
                    );
                return;
            }

            results.AddRange(
                ResolveItemRequirement(
                    condition.SourceId,
                    entry,
                    currentScene,
                    session,
                    questTrail,
                    itemTrail,
                    ItemRequirementSemanticKind.Objective,
                    giverNodeId: -1,
                    tracer
                )
            );
        }

    private IReadOnlyList<ResolvedTarget>? ResolveBlockingUnlockRequirements(
            int targetNodeId,
            FrontierEntry entry,
            string currentScene,
            ResolutionSession session,
            HashSet<int> questTrail,
            HashSet<int> itemTrail,
            IResolutionTracer? tracer = null
        )
        {
            var groups = _unlocks.GetBlockingRequirementGroups(targetNodeId);
            if (groups.Count == 0)
                return null;

            return ResolveCached(
                session.UnlockRequirementCache,
                session.ActiveUnlockRequirements,
                (entry.QuestIndex, (byte)entry.Phase, entry.RequiredForQuestIndex, targetNodeId),
                () =>
                {
                    var results = new List<ResolvedTarget>();
                    for (int groupIndex = 0; groupIndex < groups.Count; groupIndex++)
                    {
                        foreach (var condition in groups[groupIndex])
                            ResolveUnlockCondition(
                                condition,
                                entry,
                                currentScene,
                                results,
                                session,
                                questTrail,
                                itemTrail,
                                tracer
                            );
                    }
                    return FreezeResults(results);
                }
            );
        }

    private IReadOnlyList<ResolvedTarget> ResolveRecipeMaterials(
            int recipeNodeId,
            FrontierEntry entry,
            string currentScene,
            ResolutionSession session,
            HashSet<int> questTrail,
            HashSet<int> itemTrail,
            IResolutionTracer? tracer = null
        )
        {
            return ResolveCached(
                session.RecipeMaterialCache,
                session.ActiveRecipeMaterials,
                (entry.QuestIndex, (byte)entry.Phase, entry.RequiredForQuestIndex, recipeNodeId),
                () =>
                {
                    var results = new List<ResolvedTarget>();
                    foreach (
                        var materialEdge in _guide.OutEdges(
                            _guide.GetNodeKey(recipeNodeId),
                            EdgeType.RequiresMaterial
                        )
                    )
                    {
                        if (!_guide.TryGetNodeId(materialEdge.Target, out int materialId))
                            continue;

                        int materialIndex = _guide.FindItemIndex(materialId);
                        if (
                            materialIndex >= 0
                            && _phases.GetItemCount(materialIndex) >= (materialEdge.Quantity ?? 1)
                        )
                            continue;

                        results.AddRange(
                            ResolveItemRequirement(
                                materialId,
                                entry,
                                currentScene,
                                session,
                                questTrail,
                                itemTrail,
                                ItemRequirementSemanticKind.Objective,
                                giverNodeId: -1,
                                tracer
                            )
                        );
                    }
                    return FreezeResults(results);
                }
            );
        }

    private void EmitNodePosition(
        int targetNodeId,
        int positionNodeId,
        ResolvedTargetRole role,
        ResolvedActionSemantic semantic,
        FrontierEntry entry,
        List<ResolvedTarget> results,
        IResolutionTracer? tracer = null
    )
    {
        if (_unlocks.Evaluate(targetNodeId, tracer) == UnlockResult.Blocked)
            return;

        var node = _guide.GetNode(positionNodeId);
        if (node == null)
            return;

        if (
            TryEmitMutableNodePositions(
                targetNodeId,
                positionNodeId,
                node,
                role,
                semantic,
                entry,
                results,
                tracer
            )
        )
            return;

        var scene = _guide.GetScene(positionNodeId);
        results.Add(
            new ResolvedTarget(
                targetNodeId,
                positionNodeId,
                role,
                semantic,
                node.X ?? float.NaN,
                node.Y ?? float.NaN,
                node.Z ?? float.NaN,
                scene,
                false,
                true,
                entry.QuestIndex,
                entry.RequiredForQuestIndex
            )
        );
        tracer?.OnTargetMaterialized(targetNodeId, positionNodeId, role.ToString(), scene, true);
    }

    private bool TryEmitMutableNodePositions(
        int targetNodeId,
        int positionNodeId,
        Node node,
        ResolvedTargetRole role,
        ResolvedActionSemantic semantic,
        FrontierEntry entry,
        List<ResolvedTarget> results,
        IResolutionTracer? tracer
    )
    {
        if (node.Type is not NodeType.MiningNode and not NodeType.ItemBag)
            return false;

        var resolvedPositions = new List<ResolvedPosition>();
        _positionResolvers.Resolve(node.Key, resolvedPositions);
        if (resolvedPositions.Count == 0)
            return false;

        for (int i = 0; i < resolvedPositions.Count; i++)
        {
            var position = resolvedPositions[i];
            results.Add(
                new ResolvedTarget(
                    targetNodeId,
                    positionNodeId,
                    role,
                    semantic,
                    position.X,
                    position.Y,
                    position.Z,
                    position.Scene,
                    false,
                    position.IsActionable,
                    entry.QuestIndex,
                    entry.RequiredForQuestIndex
                )
            );
            tracer?.OnTargetMaterialized(
                targetNodeId,
                positionNodeId,
                role.ToString(),
                position.Scene,
                position.IsActionable
            );
        }

        return true;
    }

    private void EmitSourceTargets(
        SourceSiteEntry source,
        ResolvedTargetRole role,
        ResolvedActionSemantic semantic,
        FrontierEntry entry,
        List<ResolvedTarget> results,
        IResolutionTracer? tracer = null
    )
    {
        if (source.Positions.Length == 0)
        {
            EmitNodePosition(
                source.SourceId,
                source.SourceId,
                role,
                semantic,
                entry,
                results,
                tracer
            );
            return;
        }

        var sourceNode = _guide.GetNode(source.SourceId);
        if (sourceNode is { Type: NodeType.MiningNode or NodeType.ItemBag })
        {
            TryEmitMutableNodePositions(
                source.SourceId,
                source.SourceId,
                sourceNode,
                role,
                semantic,
                entry,
                results,
                tracer
            );
            return;
        }

        string? scene = _guide.GetSourceScene(source);
        foreach (var position in source.Positions)

        {
            WorldPosition? live = _livePositions.GetLivePosition(position.SpawnId);
            bool isActionable = _livePositions.IsAlive(position.SpawnId);
            results.Add(
                new ResolvedTarget(
                    source.SourceId,
                    position.SpawnId,
                    role,
                    semantic,
                    live?.X ?? position.X,
                    live?.Y ?? position.Y,
                    live?.Z ?? position.Z,
                    scene,
                    live.HasValue,
                    isActionable,
                    entry.QuestIndex,
                    entry.RequiredForQuestIndex
                )
            );
            tracer?.OnTargetMaterialized(
                source.SourceId,
                position.SpawnId,
                role.ToString(),
                scene,
                isActionable
            );
        }
    }

    private List<SourceSiteEntry> GetVisibleItemSources(
        int itemIndex,
        IResolutionTracer? tracer = null
    )
    {
        ReadOnlySpan<SourceSiteEntry> sources = _guide.GetItemSources(itemIndex);
        bool hasHostileDrop = false;
        for (int i = 0; i < sources.Length && !hasHostileDrop; i++)
        {
            if (sources[i].EdgeType == EdgeDropsItem && IsHostileDropSource(sources[i]))
                hasHostileDrop = true;
        }

        var visible = new List<SourceSiteEntry>(sources.Length);
        int suppressed = 0;
        for (int i = 0; i < sources.Length; i++)
        {
            var source = sources[i];
            if (hasHostileDrop && source.EdgeType == EdgeDropsItem && !IsHostileDropSource(source))
            {
                suppressed++;
                continue;
            }
            visible.Add(source);
        }

        if (suppressed > 0)
            tracer?.OnHostileDropFilter(itemIndex, sources.Length, suppressed);

        return visible;
    }

    private bool IsHostileDropSource(SourceSiteEntry source) =>
        !_guide.GetNode(source.SourceId).IsFriendly;

    private ResolvedActionSemantic BuildGiverSemantic(int questIndex, int giverId)
    {
        int questNodeId = _guide.QuestNodeId(questIndex);
        bool repeatable = _guide.GetNode(questNodeId).Repeatable;
        QuestMarkerKind markerKind = repeatable
            ? QuestMarkerKind.QuestGiverRepeat
            : QuestMarkerKind.QuestGiver;

        var giverNode = _guide.GetNode(giverId);
        ResolvedActionKind actionKind = giverNode.Type switch
        {
            NodeType.Item or NodeType.Book => ResolvedActionKind.Read,
            NodeType.Zone => ResolvedActionKind.Travel,
            NodeType.Quest => ResolvedActionKind.CompleteQuest,
            _ => ResolvedActionKind.Talk,
        };

        return new ResolvedActionSemantic(
            NavigationGoalKind.StartQuest,
            DetermineTargetKind(giverId),
            actionKind,
            goalNodeKey: _guide.GetNodeKey(questNodeId),
            goalQuantity: null,
            keywordText: null,
            payloadText: null,
            targetIdentityText: _guide.GetDisplayName(giverId),
            contextText: _guide.GetDisplayName(questNodeId),
            rationaleText: null,
            zoneText: _guide.GetZoneDisplay(_guide.GetScene(giverId)),
            availabilityText: null,
            preferredMarkerKind: markerKind,
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(markerKind)
        );
    }

    private ResolvedActionSemantic BuildSourceSemantic(int itemNodeId, SourceSiteEntry source)
    {
        var actionKind = source.EdgeType switch
        {
            EdgeDropsItem => ResolvedActionKind.Kill,
            EdgeSellsItem => ResolvedActionKind.Buy,
            EdgeGivesItem => ResolvedActionKind.Talk,
            EdgeYieldsItem => DetermineYieldAction(source.SourceType),
            EdgeContains => ResolvedActionKind.Collect,
            EdgeProduces => ResolvedActionKind.Collect,
            _ => ResolvedActionKind.Collect,
        };

        return new ResolvedActionSemantic(
            NavigationGoalKind.CollectItem,
            DetermineTargetKind(source.SourceId),
            actionKind,
            goalNodeKey: _guide.GetNodeKey(itemNodeId),
            goalQuantity: null,
            keywordText: null,
            payloadText: _guide.GetDisplayName(itemNodeId),
            targetIdentityText: _guide.GetDisplayName(source.SourceId),
            contextText: null,
            rationaleText: BuildSourceRationale(itemNodeId, actionKind),
            zoneText: _guide.GetZoneDisplay(_guide.GetSourceScene(source)),
            availabilityText: null,
            preferredMarkerKind: QuestMarkerKind.Objective,
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(
                QuestMarkerKind.Objective
            )
        );
    }

    private ResolvedActionSemantic BuildStepSemantic(StepEntry step)
    {
        ResolvedActionKind actionKind = step.StepType switch
        {
            2 => ResolvedActionKind.Talk,
            3 => ResolvedActionKind.Kill,
            4 => ResolvedActionKind.Travel,
            5 => ResolvedActionKind.ShoutKeyword,
            6 => ResolvedActionKind.Read,
            _ => ResolvedActionKind.Talk,
        };

        NavigationGoalKind goalKind = step.StepType switch
        {
            3 => NavigationGoalKind.KillTarget,
            4 => NavigationGoalKind.TravelToZone,
            6 => NavigationGoalKind.ReadItem,
            _ => NavigationGoalKind.TalkToTarget,
        };

        return new ResolvedActionSemantic(
            goalKind,
            DetermineTargetKind(step.TargetId),
            actionKind,
            goalNodeKey: _guide.GetNodeKey(step.TargetId),
            goalQuantity: null,
            keywordText: null,
            payloadText: null,
            targetIdentityText: _guide.GetDisplayName(step.TargetId),
            contextText: null,
            rationaleText: null,
            zoneText: _guide.GetZoneDisplay(_guide.GetScene(step.TargetId)),
            availabilityText: null,
            preferredMarkerKind: QuestMarkerKind.Objective,
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(
                QuestMarkerKind.Objective
            )
        );
    }

    private ResolvedActionSemantic BuildTurnInSemantic(int questIndex, int completerId)
    {
        int questNodeId = _guide.QuestNodeId(questIndex);
        bool repeatable = _guide.GetNode(questNodeId).Repeatable;
        bool hasPayload = _guide.RequiredItems(questIndex).Length > 0;
        QuestMarkerKind markerKind = repeatable
            ? QuestMarkerKind.TurnInRepeatReady
            : QuestMarkerKind.TurnInReady;
        string? payload = hasPayload
            ? string.Join(
                ", ",
                _guide
                    .RequiredItems(questIndex)
                    .ToArray()
                    .Select(req => _guide.GetDisplayName(req.ItemId))
            )
            : null;
        return new ResolvedActionSemantic(
            NavigationGoalKind.CompleteQuest,
            DetermineTargetKind(completerId),
            hasPayload ? ResolvedActionKind.Give : ResolvedActionKind.Talk,
            goalNodeKey: _guide.GetNodeKey(questNodeId),
            goalQuantity: null,
            keywordText: null,
            payloadText: payload,
            targetIdentityText: _guide.GetDisplayName(completerId),
            contextText: null,
            rationaleText: null,
            zoneText: _guide.GetZoneDisplay(_guide.GetScene(completerId)),
            availabilityText: null,
            preferredMarkerKind: markerKind,
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(markerKind)
        );
    }

    private static ResolvedActionKind DetermineYieldAction(byte sourceType) =>
        sourceType switch
        {
            (byte)NodeType.MiningNode => ResolvedActionKind.Mine,
            (byte)NodeType.Water => ResolvedActionKind.Fish,
            _ => ResolvedActionKind.Collect,
        };

    private string BuildSourceRationale(int itemNodeId, ResolvedActionKind actionKind) =>
        actionKind switch
        {
            ResolvedActionKind.Kill => $"Drops {_guide.GetDisplayName(itemNodeId)}",
            ResolvedActionKind.Buy => $"Sells {_guide.GetDisplayName(itemNodeId)}",
            ResolvedActionKind.Talk => $"Gives {_guide.GetDisplayName(itemNodeId)}",
            _ => _guide.GetDisplayName(itemNodeId),
        };

    private NavigationTargetKind DetermineTargetKind(int nodeId)
    {
        NodeType nodeType = _guide.GetNode(nodeId).Type;
        return nodeType switch
        {
            NodeType.Character => NavigationTargetKind.Character,
            NodeType.Item => NavigationTargetKind.Item,
            NodeType.Quest => NavigationTargetKind.Quest,
            NodeType.Zone => NavigationTargetKind.Zone,
            NodeType.ZoneLine => NavigationTargetKind.ZoneLine,
            _ => NavigationTargetKind.Object,
        };
    }
}
