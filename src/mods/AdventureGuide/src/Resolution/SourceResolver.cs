using AdventureGuide.CompiledGuide;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Position;
using AdventureGuide.State;

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
        ResolvedTargetAvailabilityPriority availabilityPriority =
            ResolvedTargetAvailabilityPriority.Immediate,
        bool isGuaranteedLoot = false
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
        IsGuaranteedLoot = isGuaranteedLoot;
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

    public bool IsGuaranteedLoot { get; }
}

public sealed class SourceResolver
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;
    private readonly EffectiveFrontier _frontier;
    private readonly UnlockPredicateEvaluator _unlocks;

    private readonly ILivePositionProvider _livePositions;
    private readonly IResolutionLiveState? _liveState;
    private readonly PositionResolverRegistry _positionResolvers;
    private readonly ZoneRouter? _zoneRouter;

    private const byte EdgeDropsItem = (byte)EdgeType.DropsItem;
    private const byte EdgeSellsItem = (byte)EdgeType.SellsItem;
    private const byte EdgeGivesItem = (byte)EdgeType.GivesItem;
    private const byte EdgeYieldsItem = (byte)EdgeType.YieldsItem;
    private const byte EdgeContains = (byte)EdgeType.Contains;
    private const byte EdgeProduces = (byte)EdgeType.Produces;
    private const int NoBlockedRouteNodeId = -1;

    public SourceResolver(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        UnlockPredicateEvaluator unlocks,
        ILivePositionProvider livePositions,
        PositionResolverRegistry positionResolvers,
        ZoneRouter? zoneRouter = null,
        IResolutionLiveState? liveState = null
    )
    {
        _guide = guide;
        _phases = phases;
        _frontier = new EffectiveFrontier(guide, phases);
        _unlocks = unlocks;

        _livePositions = livePositions;
        _positionResolvers = positionResolvers;
        _zoneRouter = zoneRouter;
        _liveState = liveState;
    }

    internal sealed class ResolutionSession
    {
        // Prerequisite quest walks are memoized per resolution batch. The cache is
        // local scratch for SourceResolver's recursive walk; engine-level queries own
        // durable maintained-view caching.
        internal readonly Dictionary<int, IReadOnlyList<ResolvedTarget>> QuestFrontierCache = new();
        internal readonly HashSet<int> ActiveQuestFrontiers = new();

        // ItemRequirementCache semantics depend on entry.QuestIndex through
        // BuildGiverSemantic / BuildGiverAcquisitionSemantic (ReadyToAccept giver
        // paths). Two sibling quests sharing the same (Phase, RequiredForQuestIndex,
        // ItemNodeId, SemanticKind, GiverNodeId) would otherwise reuse the first
        // caller's semantics — a latent cross-wiring bug. Including QuestIndex in
        // the key makes the cache per-caller correct.
        internal readonly Dictionary<
            (
                byte Phase,
                int QuestIndex,
                int RequiredForQuestIndex,
                int ItemNodeId,
                byte SemanticKind,
                int GiverNodeId
            ),
            IReadOnlyList<ResolvedTarget>
        > ItemRequirementCache = new();
        internal readonly HashSet<(
            byte Phase,
            int QuestIndex,
            int RequiredForQuestIndex,
            int ItemNodeId,
            byte SemanticKind,
            int GiverNodeId
        )> ActiveItemRequirements = new();

        internal readonly Dictionary<
            (
                byte Phase,
                int TargetNodeId,
                int RouteNodeId,
                int QuestIndex,
                int RequiredForQuestIndex
            ),
            IReadOnlyList<ResolvedTarget>
        > UnlockRequirementCache = new();
        internal readonly HashSet<(
            byte Phase,
            int TargetNodeId,
            int RouteNodeId,
            int QuestIndex,
            int RequiredForQuestIndex
        )> ActiveUnlockRequirements = new();

        internal readonly Dictionary<
            (byte Phase, int RecipeNodeId, int QuestIndex, int RequiredForQuestIndex),
            IReadOnlyList<ResolvedTarget>
        > RecipeMaterialCache = new();
        internal readonly HashSet<(
            byte Phase,
            int RecipeNodeId,
            int QuestIndex,
            int RequiredForQuestIndex
        )> ActiveRecipeMaterials = new();

        // UnlockPredicateEvaluator.GetBlockingRequirementGroups is a pure function
        // of targetNodeId + the current QuestPhaseTracker snapshot. Phase state is
        // stable across one resolution batch, so each unique node ID resolves once
        // per batch instead of once per emission site (thousands -> tens in the
        // evidence from F6 profiling).
        internal readonly Dictionary<
            int,
            IReadOnlyList<IReadOnlyList<UnlockConditionEntry>>
        > BlockingGroupsCache = new();

        // Scratch trails reused across top-level ResolveTargets calls within a
        // batch. Re-entrant query-owned prerequisite reads must not reuse these
        // same HashSets while an outer resolve is still walking, so ResolveTargets
        // falls back to fresh local sets whenever ResolveCallDepth > 0.
        internal readonly HashSet<int> QuestTrailScratch = new();
        internal readonly HashSet<int> ItemTrailScratch = new();
        internal int ResolveCallDepth;

        // QuestTargetResolver.Resolve dedupes per call by
        // (questKey, goalKey, targetKey, scene, positionKey). Pool the dedupe
        // set on the session so the per-batch fan-out across quests doesn't
        // allocate a fresh HashSet for every call. Re-entrant child quest reads
        // must fall back to a local set while an outer SourceResolver walk is
        // still active, matching the trail scratch contract above.
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

    private static IReadOnlyList<ResolvedTarget> FreezeResultsByAvailabilityPriority(
        List<ResolvedTarget> results
    )
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
            availabilityPriority,
            isGuaranteedLoot: target.IsGuaranteedLoot
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
        bool useScratch = session.ResolveCallDepth == 0;
        var questTrail = useScratch ? session.QuestTrailScratch : new HashSet<int>();
        var itemTrail = useScratch ? session.ItemTrailScratch : new HashSet<int>();
        if (useScratch)
        {
            questTrail.Clear();
            itemTrail.Clear();
        }

        session.ResolveCallDepth++;
        try
        {
            ResolveEntry(entry, currentScene, results, session, questTrail, itemTrail, tracer);
        }
        finally
        {
            session.ResolveCallDepth--;
        }

        return FreezeResultsByAvailabilityPriority(results);
    }

    /// <summary>
    /// Walk one frontier entry and emit every <see cref="ResolvedTarget"/> the
    /// player needs to act on to advance the quest.
    ///
    /// Dispatches on <see cref="FrontierEntry.Phase"/>:
    /// <list type="bullet">
    ///   <item><see cref="QuestPhase.ReadyToAccept"/> — walk the quest's givers.
    ///     Item/book givers route through <see cref="ResolveItemRequirement"/>
    ///     with <c>GiverInteraction</c> when the player already holds the token
    ///     or <c>GiverAcquisition</c> otherwise. Quest givers recurse into the
    ///     giver quest via <see cref="ResolveQuestFrontier"/>. Character/world
    ///     givers emit directly.</item>
    ///   <item><see cref="QuestPhase.Accepted"/> — walk required items first,
    ///     routing each missing item through <see cref="ResolveItemRequirement"/>
    ///     as an <c>Objective</c>. If every requirement is met, emit the quest's
    ///     completers as turn-in targets.</item>
    /// </list>
    ///
    /// <paramref name="questTrail"/> prevents infinite recursion through quest
    /// prerequisites; the entry returns early if its quest is already on the
    /// trail and pops itself in the finally block.
    /// </summary>
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
                            bool hasGiverItem =
                                giverItemIndex >= 0 && _phases.GetItemCount(giverItemIndex) > 0;
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
        IReadOnlyList<ResolvedTarget> cached;
        // Inlined ResolveCached pattern: avoids a Func<...> closure allocation
        // on every invocation. Same semantics as the original helper — check the
        // cache first, guard against re-entrancy via the active set, run the
        // builder on cache miss, then store. The finally block keeps the active
        // set consistent even if the builder throws.
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
                    _frontier.Resolve(questIndex, frontier, -1, tracer);
                    var results = new List<ResolvedTarget>();
                    for (int i = 0; i < frontier.Count; i++)
                        ResolveEntry(
                            frontier[i],
                            currentScene,
                            results,
                            session,
                            questTrail,
                            itemTrail,
                            tracer
                        );
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
        int unboundCount = 0;
        for (int i = 0; i < targets.Count; i++)
        {
            if (targets[i].RequiredForQuestIndex < 0)
                unboundCount++;
        }

        if (unboundCount == 0)
            return targets;

        var rebound = new List<ResolvedTarget>(targets.Count);
        for (int i = 0; i < targets.Count; i++)
        {
            var target = targets[i];
            rebound.Add(
                target.RequiredForQuestIndex < 0
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
            target.AvailabilityPriority,
            isGuaranteedLoot: target.IsGuaranteedLoot
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
                            ItemRequirementSemanticKind.GiverInteraction => BuildGiverSemantic(
                                entry.QuestIndex,
                                giverNodeId
                            ),
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
            itemNodeId,
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
        IReadOnlyList<IReadOnlyList<UnlockConditionEntry>> routeGroups = Array.Empty<
            IReadOnlyList<UnlockConditionEntry>
        >();
        if (
            TryGetBlockedRouteNodeId(currentScene, targetScene, out routeNodeId)
            && routeNodeId != targetNodeId
        )
            routeGroups = GetBlockingGroupsCached(session, routeNodeId);
        if (directGroups.Count == 0 && routeGroups.Count == 0)
            return null;

        var childEntry = new FrontierEntry(
            entry.QuestIndex,
            entry.Phase,
            entry.RequiredForQuestIndex
        );
        // Inlined ResolveCached pattern: avoids a Func<...> closure allocation.
        var key = (
            (byte)entry.Phase,
            targetNodeId,
            routeNodeId,
            entry.QuestIndex,
            entry.RequiredForQuestIndex
        );
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
                        childEntry,
                        currentScene,
                        results,
                        session,
                        questTrail,
                        itemTrail,
                        tracer
                    );
                    AppendUnlockConditionTargets(
                        routeGroups,
                        childEntry,
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
            cached,
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
        var childEntry = new FrontierEntry(
            entry.QuestIndex,
            entry.Phase,
            entry.RequiredForQuestIndex
        );
        // Inlined ResolveCached pattern: avoids a Func<...> closure allocation.
        var key = ((byte)entry.Phase, recipeNodeId, entry.QuestIndex, entry.RequiredForQuestIndex);
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
                                childEntry,
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
            cached,
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
        int itemNodeId,
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

        if (source.EdgeType == EdgeDropsItem)
            EmitDropLootTargets(itemNodeId, source, sourceNode, role, entry, results);

        if (source.Positions.Length == 0)
        {
            if (
                sourceNode.Type == NodeType.Character
                && TryEmitCharacterSpawnTargets(
                    itemNodeId,
                    source.SourceId,
                    role,
                    semantic,
                    entry,
                    results,
                    tracer
                )
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

    private void EmitDropLootTargets(
        int itemNodeId,
        SourceSiteEntry source,
        Node sourceNode,
        ResolvedTargetRole role,
        FrontierEntry entry,
        List<ResolvedTarget> results
    )
    {
        if (_liveState == null)
            return;

        var itemNode = _guide.GetNode(itemNodeId);
        if (itemNode == null)
            return;

        foreach (var chest in _liveState.GetRotChestPositionsWithItem(itemNode.Key))
        {
            results.Add(
                new ResolvedTarget(
                    source.SourceId,
                    source.SourceId,
                    role,
                    ResolvedActionSemanticBuilder.BuildForLootChest(
                        itemNode,
                        sourceNode,
                        chest.Scene
                    ),
                    chest.X,
                    chest.Y,
                    chest.Z,
                    chest.Scene,
                    isLive: true,
                    isActionable: true,
                    entry.QuestIndex,
                    entry.RequiredForQuestIndex,
                    isGuaranteedLoot: true
                )
            );
        }

        for (int i = 0; i < source.Positions.Length; i++)
        {
            var position = source.Positions[i];
            var spawnNode = _guide.GetNode(position.SpawnId);
            if (spawnNode == null)
                continue;

            TryEmitCorpseLootTarget(
                itemNodeId,
                source.SourceId,
                position.SpawnId,
                spawnNode,
                role,
                entry,
                results
            );
        }
    }

    private bool TryEmitCorpseLootTarget(
        int itemNodeId,
        int sourceNodeId,
        int spawnNodeId,
        Node spawnNode,
        ResolvedTargetRole role,
        FrontierEntry entry,
        List<ResolvedTarget> results
    )
    {
        if (_liveState == null)
            return false;

        var itemNode = _guide.GetNode(itemNodeId);
        var sourceNode = _guide.GetNode(sourceNodeId);
        if (itemNode == null || sourceNode == null)
            return false;

        if (!_liveState.TryGetCorpsePositionWithItem(spawnNode, itemNode.Key, out var corpse))
            return false;

        results.Add(
            new ResolvedTarget(
                sourceNodeId,
                spawnNodeId,
                role,
                ResolvedActionSemanticBuilder.BuildForCorpseLoot(
                    itemNode,
                    sourceNode,
                    corpse.Scene
                ),
                corpse.X,
                corpse.Y,
                corpse.Z,
                corpse.Scene,
                isLive: true,
                isActionable: true,
                entry.QuestIndex,
                entry.RequiredForQuestIndex,
                isGuaranteedLoot: true
            )
        );
        return true;
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
        int itemNodeId,
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
            if (
                spawnNode == null
                || spawnNode.X is null
                || spawnNode.Y is null
                || spawnNode.Z is null
            )
                continue;

            if (semantic.ActionKind == ResolvedActionKind.Kill)
                TryEmitCorpseLootTarget(
                    itemNodeId,
                    sourceNodeId,
                    spawnNodeId,
                    spawnNode,
                    role,
                    entry,
                    results
                );

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

    private ResolvedActionSemantic BuildReadStepAcquisitionSemantic(
        int itemNodeId,
        SourceSiteEntry source
    ) =>
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
        string? sourceScene =
            sourceNode == null
                ? _guide.GetSourceScene(source)
                : ResolveSourceScene(source, sourceNode);
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
