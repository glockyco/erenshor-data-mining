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

public enum ResolvedTargetAvailabilityPriority : byte
{
    Immediate = 0,
    PrerequisiteFallback = 1,
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
        int requiredForQuestIndex,
        ResolvedTargetAvailabilityPriority availabilityPriority = ResolvedTargetAvailabilityPriority.Immediate
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
        AvailabilityPriority = availabilityPriority;
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
    public ResolvedTargetAvailabilityPriority AvailabilityPriority { get; }
}

public sealed class SourceResolver
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;
    private readonly EffectiveFrontier _frontier;
    private readonly UnlockPredicateEvaluator _unlocks;

    private readonly ILivePositionProvider _livePositions;
    private readonly PositionResolverRegistry _positionResolvers;
    private readonly ZoneRouter? _zoneRouter;


    private const byte EdgeDropsItem = (byte)EdgeType.DropsItem;
    private const byte EdgeSellsItem = (byte)EdgeType.SellsItem;
    private const byte EdgeGivesItem = (byte)EdgeType.GivesItem;
    private const byte EdgeYieldsItem = (byte)EdgeType.YieldsItem;
    private const byte EdgeContains = (byte)EdgeType.Contains;
    private const byte EdgeProduces = (byte)EdgeType.Produces;
    private const int NoBlockedRouteNodeId = -1;
    private const int DeferredRequiredForQuestIndex = int.MinValue;



    public SourceResolver(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        UnlockPredicateEvaluator unlocks,
        ILivePositionProvider livePositions,
        PositionResolverRegistry positionResolvers,
        ZoneRouter? zoneRouter = null
    )
    {
        _guide = guide;
        _phases = phases;
        _frontier = new EffectiveFrontier(guide, phases);
        _unlocks = unlocks;

        _livePositions = livePositions;
        _positionResolvers = positionResolvers;
        _zoneRouter = zoneRouter;
    }


    internal sealed class ResolutionSession
    {
        public readonly Dictionary<int, IReadOnlyList<ResolvedTarget>> QuestFrontierCache = new();
        public readonly HashSet<int> ActiveQuestFrontiers = new();
        public readonly Dictionary<
            (byte Phase, int RequiredForQuestIndex, int ItemNodeId, byte SemanticKind, int GiverNodeId),
            IReadOnlyList<ResolvedTarget>
        > ItemRequirementCache = new();
        public readonly HashSet<
            (byte Phase, int RequiredForQuestIndex, int ItemNodeId, byte SemanticKind, int GiverNodeId)
        > ActiveItemRequirements = new();
        public readonly Dictionary<
            (byte Phase, int RequiredForQuestIndex, int TargetNodeId, int RouteNodeId),
            IReadOnlyList<ResolvedTarget>
        > UnlockRequirementCache = new();
        public readonly HashSet<
            (byte Phase, int RequiredForQuestIndex, int TargetNodeId, int RouteNodeId)
        > ActiveUnlockRequirements = new();
        public readonly Dictionary<
            (byte Phase, int RequiredForQuestIndex, int RecipeNodeId),
            IReadOnlyList<ResolvedTarget>
        > RecipeMaterialCache = new();
        public readonly HashSet<
            (byte Phase, int RequiredForQuestIndex, int RecipeNodeId)
        > ActiveRecipeMaterials = new();

        // UnlockPredicateEvaluator.GetBlockingRequirementGroups is a pure function
        // of targetNodeId + the current QuestPhaseTracker snapshot. Phase state is
        // stable across one resolution batch, so each unique node ID resolves once
        // per batch instead of once per emission site (thousands -> tens in the
        // evidence from F6 profiling).
        public readonly Dictionary<int, IReadOnlyList<IReadOnlyList<UnlockConditionEntry>>> BlockingGroupsCache = new();
    }

    private enum ItemRequirementSemanticKind : byte
    {
        Objective = 0,
        GiverInteraction = 1,
        GiverAcquisition = 2,
        ReadStepAcquisition = 3,
    }

    private static IReadOnlyList<ResolvedTarget> FreezeResults(List<ResolvedTarget> results) =>
        results.Count == 0 ? Array.Empty<ResolvedTarget>() : results;

    private static IReadOnlyList<ResolvedTarget> FreezeResultsByAvailabilityPriority(List<ResolvedTarget> results)
    {
        if (results.Count < 2)
            return FreezeResults(results);

        int fallbackIndex = -1;
        for (int i = 0; i < results.Count; i++)
        {
            if (results[i].AvailabilityPriority != ResolvedTargetAvailabilityPriority.Immediate)
            {
                fallbackIndex = i;
                break;
            }
        }

        if (fallbackIndex < 0)
            return FreezeResults(results);

        var ordered = new List<ResolvedTarget>(results.Count);
        for (int i = 0; i < results.Count; i++)
        {
            if (results[i].AvailabilityPriority == ResolvedTargetAvailabilityPriority.Immediate)
                ordered.Add(results[i]);
        }
        for (int i = 0; i < results.Count; i++)
        {
            if (results[i].AvailabilityPriority != ResolvedTargetAvailabilityPriority.Immediate)
                ordered.Add(results[i]);
        }

        return FreezeResults(ordered);
    }

    private static IReadOnlyList<ResolvedTarget> RebindAvailabilityPriority(
        IReadOnlyList<ResolvedTarget> targets,
        ResolvedTargetAvailabilityPriority availabilityPriority
    )
    {
        if (targets.Count == 0)
            return targets;

        bool needsRebind = false;
        for (int i = 0; i < targets.Count; i++)
        {
            if (targets[i].AvailabilityPriority != availabilityPriority)
            {
                needsRebind = true;
                break;
            }
        }

        if (!needsRebind)
            return targets;

        var rebound = new List<ResolvedTarget>(targets.Count);
        for (int i = 0; i < targets.Count; i++)
            rebound.Add(RebindAvailabilityPriority(targets[i], availabilityPriority));
        return FreezeResults(rebound);
    }

    private static ResolvedTarget RebindAvailabilityPriority(
        ResolvedTarget target,
        ResolvedTargetAvailabilityPriority availabilityPriority
    ) =>
        new(
            target.TargetNodeId,
            target.PositionNodeId,
            target.Role,
            target.Semantic,
            target.X,
            target.Y,
            target.Z,
            target.Scene,
            target.IsLive,
            target.IsActionable,
            target.QuestIndex,
            target.RequiredForQuestIndex,
            availabilityPriority
        );

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
        return FreezeResultsByAvailabilityPriority(results);
    }

    internal IReadOnlyList<ResolvedTarget> ResolveUnlockTargets(
        int targetNodeId,
        FrontierEntry entry,
        string currentScene,
        ResolutionSession session,
        IResolutionTracer? tracer = null
    )
    {
        string? targetScene = _guide.GetNode(targetNodeId)?.Scene;
        var results = ResolveBlockingRequirements(
            targetNodeId,
            targetScene,
            entry,
            currentScene,
            session,
            new HashSet<int>(),
            new HashSet<int>(),
            tracer
        );
        return results == null
            ? Array.Empty<ResolvedTarget>()
            : RebindAvailabilityPriority(results, ResolvedTargetAvailabilityPriority.PrerequisiteFallback);
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
                                int giverItemIndex = _guide.FindItemIndex(giverId);
                                bool hasGiverItem = giverItemIndex >= 0 && _phases.GetItemCount(giverItemIndex) > 0;
                                results.AddRange(
                                    ResolveItemRequirement(
                                        giverId,
                                        entry,
                                        currentScene,
                                        session,
                                        questTrail,
                                        itemTrail,
                                        hasGiverItem
                                            ? ItemRequirementSemanticKind.GiverInteraction
                                            : ItemRequirementSemanticKind.GiverAcquisition,
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
                                currentScene,
                                results,
                                session,
                                questTrail,
                                itemTrail,
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
                            var stepTargetNode = _guide.GetNode(step.TargetId);
                            bool unreadItemStep =
                                step.StepType == StepLabels.Read
                                && stepTargetNode?.Type is NodeType.Item or NodeType.Book
                                && _guide.FindItemIndex(step.TargetId) is int stepItemIndex
                                && stepItemIndex >= 0
                                && _phases.GetItemCount(stepItemIndex) == 0;
                            if (unreadItemStep)
                            {
                                results.AddRange(
                                    ResolveItemRequirement(
                                        step.TargetId,
                                        entry,
                                        currentScene,
                                        session,
                                        questTrail,
                                        itemTrail,
                                        ItemRequirementSemanticKind.ReadStepAcquisition,
                                        giverNodeId: -1,
                                        tracer
                                    )
                                );
                                continue;
                            }
                            EmitNodePosition(
                                step.TargetId,
                                step.TargetId,
                                ResolvedTargetRole.Objective,
                                BuildStepSemantic(step),
                                entry,
                                currentScene,
                                results,
                                session,
                                questTrail,
                                itemTrail,
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
                                    currentScene,
                                    results,
                                    session,
                                    questTrail,
                                    itemTrail,
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
            var cached = ResolveCached(
                session.QuestFrontierCache,
                session.ActiveQuestFrontiers,
                questIndex,
                () =>
                {
                    var frontier = new List<FrontierEntry>();
                    _frontier.Resolve(
                        questIndex,
                        frontier,
                        DeferredRequiredForQuestIndex,
                        tracer
                    );
                    var results = new List<ResolvedTarget>();
                    for (int i = 0; i < frontier.Count; i++)
                        ResolveEntry(frontier[i], currentScene, results, session, questTrail, itemTrail, tracer);
                    return FreezeResults(results);
                }
            );
            return RebindAvailabilityPriority(
                ApplyRequiredForQuestIndex(cached, requiredForQuestIndex),
                ResolvedTargetAvailabilityPriority.PrerequisiteFallback
            );
        }

    private IReadOnlyList<ResolvedTarget> ApplyRequiredForQuestIndex(
        IReadOnlyList<ResolvedTarget> targets,
        int requiredForQuestIndex
    )
    {
        int deferredCount = 0;
        for (int i = 0; i < targets.Count; i++)
        {
            if (targets[i].RequiredForQuestIndex == DeferredRequiredForQuestIndex)
                deferredCount++;
        }

        if (deferredCount == 0)
            return targets;

        var rebound = new List<ResolvedTarget>(targets.Count);
        for (int i = 0; i < targets.Count; i++)
        {
            var target = targets[i];
            rebound.Add(
                target.RequiredForQuestIndex == DeferredRequiredForQuestIndex
                    ? RebindRequiredForQuestIndex(target, requiredForQuestIndex)
                    : target
            );
        }

        return FreezeResults(rebound);
    }

    private static ResolvedTarget RebindRequiredForQuestIndex(
        ResolvedTarget target,
        int requiredForQuestIndex
    ) =>
        new(
            target.TargetNodeId,
            target.PositionNodeId,
            target.Role,
            target.Semantic,
            target.X,
            target.Y,
            target.Z,
            target.Scene,
            target.IsLive,
            target.IsActionable,
            target.QuestIndex,
            requiredForQuestIndex,
            target.AvailabilityPriority
        );

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
                                var semantic = semanticKind switch
                                {
                                    ItemRequirementSemanticKind.GiverInteraction =>
                                        BuildGiverSemantic(entry.QuestIndex, giverNodeId),
                                    ItemRequirementSemanticKind.GiverAcquisition =>
                                        BuildGiverAcquisitionSemantic(entry.QuestIndex, itemNodeId, source),
                                    ItemRequirementSemanticKind.ReadStepAcquisition =>
                                        BuildReadStepAcquisitionSemantic(itemNodeId, source),
                                    _ => BuildSourceSemantic(itemNodeId, source),
                                };

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

                        return FreezeResultsByAvailabilityPriority(results);
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

            var unlockTargets = ResolveBlockingRequirements(
                source.SourceId,
                _guide.GetSourceScene(source),
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
            EmitSourceTargets(
                source,
                role,
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

    private IReadOnlyList<ResolvedTarget>? ResolveBlockingRequirements(
            int targetNodeId,
            string? targetScene,
            FrontierEntry entry,
            string currentScene,
            ResolutionSession session,
            HashSet<int> questTrail,
            HashSet<int> itemTrail,
            IResolutionTracer? tracer = null
        )
        {
            var directGroups = GetBlockingGroupsCached(session, targetNodeId);
            int routeNodeId = NoBlockedRouteNodeId;
            IReadOnlyList<IReadOnlyList<UnlockConditionEntry>> routeGroups =
                Array.Empty<IReadOnlyList<UnlockConditionEntry>>();
            if (
                TryGetBlockedRouteNodeId(currentScene, targetScene, out routeNodeId)
                && routeNodeId != targetNodeId
            )
                routeGroups = GetBlockingGroupsCached(session, routeNodeId);
            if (directGroups.Count == 0 && routeGroups.Count == 0)
                return null;

            return RebindAvailabilityPriority(
                ResolveCached(
                    session.UnlockRequirementCache,
                    session.ActiveUnlockRequirements,
                    (
                        (byte)entry.Phase,
                        entry.RequiredForQuestIndex,
                        targetNodeId,
                        routeNodeId
                    ),

                    () =>
                    {
                        var results = new List<ResolvedTarget>();
                        AppendUnlockConditionTargets(
                            directGroups,
                            entry,
                            currentScene,
                            results,
                            session,
                            questTrail,
                            itemTrail,
                            tracer
                        );
                        AppendUnlockConditionTargets(
                            routeGroups,
                            entry,
                            currentScene,
                            results,
                            session,
                            questTrail,
                            itemTrail,
                            tracer
                        );
                        return FreezeResultsByAvailabilityPriority(results);
                    }
                ),
                ResolvedTargetAvailabilityPriority.PrerequisiteFallback
            );
        }

    private IReadOnlyList<IReadOnlyList<UnlockConditionEntry>> GetBlockingGroupsCached(
        ResolutionSession session,
        int nodeId
    )
    {
        if (session.BlockingGroupsCache.TryGetValue(nodeId, out var cached))
            return cached;
        var groups = _unlocks.GetBlockingRequirementGroups(nodeId);
        session.BlockingGroupsCache[nodeId] = groups;
        return groups;
    }

    private void AppendUnlockConditionTargets(
        IReadOnlyList<IReadOnlyList<UnlockConditionEntry>> groups,
        FrontierEntry entry,
        string currentScene,
        List<ResolvedTarget> results,
        ResolutionSession session,
        HashSet<int> questTrail,
        HashSet<int> itemTrail,
        IResolutionTracer? tracer
    )
    {
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
    }

    private bool TryGetBlockedRouteNodeId(
        string currentScene,
        string? targetScene,
        out int routeNodeId
    )
    {
        routeNodeId = NoBlockedRouteNodeId;
        if (
            _zoneRouter == null
            || string.IsNullOrWhiteSpace(currentScene)
            || string.IsNullOrWhiteSpace(targetScene)
        )
            return false;
        if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
            return false;

        var lockedHop = _zoneRouter.FindFirstLockedHop(currentScene, targetScene);
        return lockedHop != null && _guide.TryGetNodeId(lockedHop.ZoneLineKey, out routeNodeId);
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
            return RebindAvailabilityPriority(
                ResolveCached(
                    session.RecipeMaterialCache,
                    session.ActiveRecipeMaterials,
                    ((byte)entry.Phase, entry.RequiredForQuestIndex, recipeNodeId),

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
                        return FreezeResultsByAvailabilityPriority(results);
                    }
                ),
                ResolvedTargetAvailabilityPriority.PrerequisiteFallback
            );
        }

    private void EmitNodePosition(
        int targetNodeId,
        int positionNodeId,
        ResolvedTargetRole role,
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
        var node = _guide.GetNode(positionNodeId);
        if (node == null)
            return;

        var unlockTargets = ResolveBlockingRequirements(
            targetNodeId,
            node.Scene,
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
        string currentScene,
        List<ResolvedTarget> results,
        ResolutionSession session,
        HashSet<int> questTrail,
        HashSet<int> itemTrail,
        IResolutionTracer? tracer = null
    )
    {
        var sourceNode = _guide.GetNode(source.SourceId);
        if (sourceNode == null)
            return;

        string? sourceScene = ResolveSourceScene(source, sourceNode);
        var unlockTargets = ResolveBlockingRequirements(
            source.SourceId,
            sourceScene,
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

        if (source.Positions.Length == 0)
        {
            if (
                sourceNode.Type == NodeType.Character
                && TryEmitCharacterSpawnTargets(source.SourceId, role, semantic, entry, results, tracer)
            )
                return;

            EmitNodePosition(
                source.SourceId,
                source.SourceId,
                role,
                semantic,
                entry,
                currentScene,
                results,
                session,
                questTrail,
                itemTrail,
                tracer
            );
            return;
        }

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
                    sourceScene,
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
                sourceScene,
                isActionable
            );
        }
    }

    private string? ResolveSourceScene(SourceSiteEntry source, Node sourceNode)
    {
        string? scene = _guide.GetSourceScene(source);
        if (!string.IsNullOrWhiteSpace(scene) || sourceNode.Type != NodeType.Character)
            return scene;

        string sourceKey = _guide.GetNodeKey(source.SourceId);
        foreach (var spawnEdge in _guide.OutEdges(sourceKey, EdgeType.HasSpawn))
        {
            var spawnNode = _guide.GetNode(spawnEdge.Target);
            if (!string.IsNullOrWhiteSpace(spawnNode?.Scene))
                return spawnNode.Scene;
        }

        return scene;
    }

    private bool TryEmitCharacterSpawnTargets(
        int sourceNodeId,
        ResolvedTargetRole role,
        ResolvedActionSemantic semantic,
        FrontierEntry entry,
        List<ResolvedTarget> results,
        IResolutionTracer? tracer
    )
    {
        string sourceKey = _guide.GetNodeKey(sourceNodeId);
        var spawnEdges = _guide.OutEdges(sourceKey, EdgeType.HasSpawn);
        if (spawnEdges.Count == 0)
            return false;

        bool emitted = false;
        for (int i = 0; i < spawnEdges.Count; i++)
        {
            if (!_guide.TryGetNodeId(spawnEdges[i].Target, out int spawnNodeId))
                continue;

            var spawnNode = _guide.GetNode(spawnNodeId);
            if (spawnNode == null || spawnNode.X is null || spawnNode.Y is null || spawnNode.Z is null)
                continue;

            WorldPosition? live = _livePositions.GetLivePosition(spawnNodeId);
            bool isActionable = _livePositions.IsAlive(spawnNodeId);
            results.Add(
                new ResolvedTarget(
                    sourceNodeId,
                    spawnNodeId,
                    role,
                    semantic,
                    live?.X ?? spawnNode.X.Value,
                    live?.Y ?? spawnNode.Y.Value,
                    live?.Z ?? spawnNode.Z.Value,
                    spawnNode.Scene,
                    live.HasValue,
                    isActionable,
                    entry.QuestIndex,
                    entry.RequiredForQuestIndex
                )
            );
            tracer?.OnTargetMaterialized(
                sourceNodeId,
                spawnNodeId,
                role.ToString(),
                spawnNode.Scene,
                isActionable
            );
            emitted = true;
        }

        return emitted;
    }


    private List<SourceSiteEntry> GetVisibleItemSources(
        int itemIndex,
        IResolutionTracer? tracer = null
    )
    {
        ReadOnlySpan<SourceSiteEntry> sources = _guide.GetItemSources(itemIndex);
        var visible = ItemSourceVisibilityPolicy.Filter(
            sources.ToArray(),
            source => (EdgeType)source.EdgeType,
            source => !_guide.GetNode(source.SourceId).IsFriendly
        );
        int suppressed = sources.Length - visible.Count;
        if (suppressed > 0)
            tracer?.OnHostileDropFilter(itemIndex, sources.Length, suppressed);
        return visible;
    }

    

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

    private ResolvedActionSemantic BuildGiverAcquisitionSemantic(
        int questIndex,
        int itemNodeId,
        SourceSiteEntry source
    ) =>
        BuildAcquisitionSemantic(
            NavigationGoalKind.StartQuest,
            _guide.GetNodeKey(_guide.QuestNodeId(questIndex)),
            _guide.GetDisplayName(_guide.QuestNodeId(questIndex)),
            itemNodeId,
            source
        );

    private ResolvedActionSemantic BuildReadStepAcquisitionSemantic(int itemNodeId, SourceSiteEntry source) =>
        BuildAcquisitionSemantic(
            NavigationGoalKind.ReadItem,
            _guide.GetNodeKey(itemNodeId),
            contextText: null,
            itemNodeId,
            source
        );

    private ResolvedActionSemantic BuildAcquisitionSemantic(
        NavigationGoalKind goalKind,
        string goalNodeKey,
        string? contextText,
        int itemNodeId,
        SourceSiteEntry source
    )
    {
        ResolvedActionKind actionKind = DetermineSourceActionKind(source);
        var sourceNode = _guide.GetNode(source.SourceId);
        string? sourceScene = sourceNode == null ? _guide.GetSourceScene(source) : ResolveSourceScene(source, sourceNode);
        return new ResolvedActionSemantic(
            goalKind,
            DetermineTargetKind(source.SourceId),
            actionKind,
            goalNodeKey,
            goalQuantity: null,
            keywordText: null,
            payloadText: _guide.GetDisplayName(itemNodeId),
            targetIdentityText: _guide.GetDisplayName(source.SourceId),
            contextText,
            rationaleText: BuildSourceRationale(itemNodeId, actionKind),
            zoneText: _guide.GetZoneDisplay(sourceScene),
            availabilityText: null,
            preferredMarkerKind: QuestMarkerKind.Objective,
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(
                QuestMarkerKind.Objective
            )
        );
    }

    private ResolvedActionSemantic BuildSourceSemantic(int itemNodeId, SourceSiteEntry source) =>
        BuildAcquisitionSemantic(
            NavigationGoalKind.CollectItem,
            _guide.GetNodeKey(itemNodeId),
            contextText: null,
            itemNodeId,
            source
        );

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

    private ResolvedActionKind DetermineSourceActionKind(SourceSiteEntry source) =>
        source.EdgeType switch
        {
            EdgeDropsItem => ResolvedActionKind.Kill,
            EdgeSellsItem => ResolvedActionKind.Buy,
            EdgeGivesItem => ResolvedActionKind.Talk,
            EdgeYieldsItem => DetermineYieldAction(source.SourceType),
            EdgeContains => ResolvedActionKind.Collect,
            EdgeProduces => ResolvedActionKind.Collect,
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
