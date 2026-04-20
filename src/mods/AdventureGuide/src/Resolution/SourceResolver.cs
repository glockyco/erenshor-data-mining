using AdventureGuide.CompiledGuide;
using AdventureGuide.Graph;
using AdventureGuide.Frontier;
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
        internal readonly Dictionary<int, IReadOnlyList<ResolvedTarget>> QuestFrontierCache = new();
        internal readonly HashSet<int> ActiveQuestFrontiers = new();

        // ItemRequirementCache semantics depend on entry.QuestIndex through
        // BuildGiverSemantic / BuildGiverAcquisitionSemantic (ReadyToAccept giver
        // paths). Two sibling quests sharing the same (Phase, RequiredForQuestIndex,
        // ItemNodeId, SemanticKind, GiverNodeId) would otherwise reuse the first
        // caller's semantics — a latent cross-wiring bug. Including QuestIndex in
        // the key makes the cache per-caller correct; callers with genuinely
        // identical requirements still hit shared results via QuestFrontierCache
        // at the outer layer.
        internal readonly Dictionary<
            (byte Phase, int QuestIndex, int RequiredForQuestIndex, int ItemNodeId, byte SemanticKind, int GiverNodeId),
            IReadOnlyList<ResolvedTarget>
        > ItemRequirementCache = new();
        internal readonly HashSet<
            (byte Phase, int QuestIndex, int RequiredForQuestIndex, int ItemNodeId, byte SemanticKind, int GiverNodeId)
        > ActiveItemRequirements = new();

        // UnlockRequirementCache output depends only on (phase, target node, route
        // node) and the downstream ResolveQuestFrontier / ResolveItemRequirement
        // results, which encode their own caller-dependence. Sharing across callers
        // with different RequiredForQuestIndex is safe — we resolve with the
        // DeferredRequiredForQuestIndex sentinel in the key and rebind the returned
        // targets' RequiredForQuestIndex at the caller boundary via
        // ApplyRequiredForQuestIndex.
        internal readonly Dictionary<
            (byte Phase, int TargetNodeId, int RouteNodeId),
            IReadOnlyList<ResolvedTarget>
        > UnlockRequirementCache = new();
        internal readonly HashSet<
            (byte Phase, int TargetNodeId, int RouteNodeId)
        > ActiveUnlockRequirements = new();

        // RecipeMaterialCache is similarly caller-independent: its inner
        // ResolveItemRequirement calls use ItemRequirementSemanticKind.Objective
        // which relies on BuildSourceSemantic (item + source, no QuestIndex). Share
        // across RequiredForQuestIndex via the deferred-sentinel pattern.
        internal readonly Dictionary<
            (byte Phase, int RecipeNodeId),
            IReadOnlyList<ResolvedTarget>
        > RecipeMaterialCache = new();
        internal readonly HashSet<
            (byte Phase, int RecipeNodeId)
        > ActiveRecipeMaterials = new();

        // UnlockPredicateEvaluator.GetBlockingRequirementGroups is a pure function
        // of targetNodeId + the current QuestPhaseTracker snapshot. Phase state is
        // stable across one resolution batch, so each unique node ID resolves once
        // per batch instead of once per emission site (thousands -> tens in the
        // evidence from F6 profiling).
        internal readonly Dictionary<int, IReadOnlyList<IReadOnlyList<UnlockConditionEntry>>> BlockingGroupsCache = new();

        // Scratch trails reused across ResolveTargets entry-point calls within a
        // batch. Safe to pool because ResolveTargets is a top-level method (not
        // recursive): each call runs its recursion with these owned trails and
        // clears them before returning. Nested cache-miss builders allocate
        // their own HashSets via new HashSet<int>() at their own boundaries.
        internal readonly HashSet<int> QuestTrailScratch = new();
        internal readonly HashSet<int> ItemTrailScratch = new();

        // QuestTargetResolver.Resolve dedupes per call by
        // (questKey, goalKey, targetKey, scene, positionKey). Pool the dedupe
        // set on the session so the per-batch fan-out across quests doesn't
        // allocate a fresh HashSet for every call. Same correctness contract
        // as the trail scratches: caller clears before use.
        internal readonly HashSet<string> SeenTargetsScratch = new(StringComparer.Ordinal);
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

    internal IReadOnlyList<ResolvedTarget> ResolveTargets(
        FrontierEntry entry,
        string currentScene,
        IResolutionTracer? tracer = null
    )
    {
        return ResolveTargets(entry, currentScene, new ResolutionSession(), tracer);
    }

    internal IReadOnlyList<ResolvedTarget> ResolveTargets(
        FrontierEntry entry,
        string currentScene,
        ResolutionSession session,
        IResolutionTracer? tracer = null
    )
    {
        var results = new List<ResolvedTarget>();
        session.QuestTrailScratch.Clear();
        session.ItemTrailScratch.Clear();
        ResolveEntry(
            entry,
            currentScene,
            results,
            session,
            session.QuestTrailScratch,
            session.ItemTrailScratch,
            tracer
        );
        return FreezeResultsByAvailabilityPriority(results);
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
            // Inlined ResolveCached pattern: avoids a Func<...> closure allocation
            // on every invocation. Same semantics as the original helper — check the
            // cache first, guard against re-entrancy via the active set, run the
            // builder on cache miss, then store. The finally block keeps the active
            // set consistent even if the builder throws.
            IReadOnlyList<ResolvedTarget> cached;
            if (!session.QuestFrontierCache.TryGetValue(questIndex, out cached!))
            {
                if (!session.ActiveQuestFrontiers.Add(questIndex))
                {
                    cached = Array.Empty<ResolvedTarget>();
                }
                else
                {
                    try
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
                        cached = FreezeResults(results);
                        session.QuestFrontierCache[questIndex] = cached;
                    }
                    finally
                    {
                        session.ActiveQuestFrontiers.Remove(questIndex);
                    }
                }
            }
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
            // Inlined ResolveCached pattern: avoids a Func<...> closure allocation
            // per call. See ResolveQuestFrontier for the rationale.
            var key = (
                (byte)entry.Phase,
                entry.QuestIndex,
                entry.RequiredForQuestIndex,
                itemNodeId,
                (byte)semanticKind,
                giverNodeId
            );
            if (session.ItemRequirementCache.TryGetValue(key, out var cached))
                return cached;
            if (!session.ActiveItemRequirements.Add(key))
                return Array.Empty<ResolvedTarget>();

            try
            {
                if (!itemTrail.Add(itemNodeId))
                {
                    var empty = Array.Empty<ResolvedTarget>();
                    session.ItemRequirementCache[key] = empty;
                    return empty;
                }

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

                    var frozen = FreezeResultsByAvailabilityPriority(results);
                    session.ItemRequirementCache[key] = frozen;
                    return frozen;
                }
                finally
                {
                    itemTrail.Remove(itemNodeId);
                }
            }
            finally
            {
                session.ActiveItemRequirements.Remove(key);
            }
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

            // Build with a DeferredRequiredForQuestIndex entry so the emitted
            // ResolvedTargets carry the sentinel. ApplyRequiredForQuestIndex below
            // substitutes the caller's actual RequiredForQuestIndex.
            var deferredEntry = new FrontierEntry(
                entry.QuestIndex,
                entry.Phase,
                DeferredRequiredForQuestIndex
            );
            // Inlined ResolveCached pattern: avoids a Func<...> closure allocation.
            var key = ((byte)entry.Phase, targetNodeId, routeNodeId);
            IReadOnlyList<ResolvedTarget> cached;
            if (!session.UnlockRequirementCache.TryGetValue(key, out cached!))
            {
                if (!session.ActiveUnlockRequirements.Add(key))
                {
                    cached = Array.Empty<ResolvedTarget>();
                }
                else
                {
                    try
                    {
                        var results = new List<ResolvedTarget>();
                        AppendUnlockConditionTargets(
                            directGroups,
                            deferredEntry,
                            currentScene,
                            results,
                            session,
                            questTrail,
                            itemTrail,
                            tracer
                        );
                        AppendUnlockConditionTargets(
                            routeGroups,
                            deferredEntry,
                            currentScene,
                            results,
                            session,
                            questTrail,
                            itemTrail,
                            tracer
                        );
                        cached = FreezeResultsByAvailabilityPriority(results);
                        session.UnlockRequirementCache[key] = cached;
                    }
                    finally
                    {
                        session.ActiveUnlockRequirements.Remove(key);
                    }
                }
            }
            return RebindAvailabilityPriority(
                ApplyRequiredForQuestIndex(cached, entry.RequiredForQuestIndex),
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
            // Recipe material requirements are caller-independent: the inner
            // ResolveItemRequirement call uses ItemRequirementSemanticKind.Objective
            // which routes to BuildSourceSemantic (item + source only, no QuestIndex).
            // Resolve with DeferredRequiredForQuestIndex and rebind at the boundary.
            var deferredEntry = new FrontierEntry(
                entry.QuestIndex,
                entry.Phase,
                DeferredRequiredForQuestIndex
            );
            // Inlined ResolveCached pattern: avoids a Func<...> closure allocation.
            var key = ((byte)entry.Phase, recipeNodeId);
            IReadOnlyList<ResolvedTarget> cached;
            if (!session.RecipeMaterialCache.TryGetValue(key, out cached!))
            {
                if (!session.ActiveRecipeMaterials.Add(key))
                {
                    cached = Array.Empty<ResolvedTarget>();
                }
                else
                {
                    try
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
                                    deferredEntry,
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
                        cached = FreezeResultsByAvailabilityPriority(results);
                        session.RecipeMaterialCache[key] = cached;
                    }
                    finally
                    {
                        session.ActiveRecipeMaterials.Remove(key);
                    }
                }
            }
            return RebindAvailabilityPriority(
                ApplyRequiredForQuestIndex(cached, entry.RequiredForQuestIndex),
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

        // Node has no pinned coordinates: no consumer can navigate to it. Skip.
        if (!node.X.HasValue || !node.Y.HasValue || !node.Z.HasValue)
            return;

        var scene = _guide.GetScene(positionNodeId);
        results.Add(
            new ResolvedTarget(
                targetNodeId,
                positionNodeId,
                role,
                semantic,
                node.X.Value,
                node.Y.Value,
                node.Z.Value,
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

            // No spawn positions, no character-spawn fallback, no pinned source
            // coordinates: no navigable target exists. Tracker summaries fall back
            // to frontier-entry text when CompiledTargets is empty.
            if (!sourceNode.X.HasValue || !sourceNode.Y.HasValue || !sourceNode.Z.HasValue)
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
        // Specialised, delegate-free filter. Saves two Func<...> allocations per
        // call plus the sources.ToArray() copy. A fresh List is still allocated so
        // nested ResolveItemRequirement calls (which can re-enter this method
        // indirectly via ResolveItemSource) don't alias the caller's enumerator.
        var visible = new List<SourceSiteEntry>(sources.Length);
        ItemSourceVisibilityPolicy.Filter(sources, _guide, visible);
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
