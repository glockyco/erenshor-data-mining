using AdventureGuide.CompiledGuide;

using AdventureGuide.Graph;

using AdventureGuide.Plan;

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
        int requiredForQuestIndex)
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

    private const byte EdgeDropsItem  = (byte)EdgeType.DropsItem;
    private const byte EdgeSellsItem  = (byte)EdgeType.SellsItem;
    private const byte EdgeGivesItem  = (byte)EdgeType.GivesItem;
    private const byte EdgeYieldsItem = (byte)EdgeType.YieldsItem;
    private const byte EdgeContains   = (byte)EdgeType.Contains;
    private const byte EdgeProduces   = (byte)EdgeType.Produces;

    public SourceResolver(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        UnlockPredicateEvaluator unlocks,
        ILivePositionProvider livePositions)
    {
        _guide = guide;
        _phases = phases;
        _unlocks = unlocks;
        _livePositions = livePositions;
    }

    public IReadOnlyList<ResolvedTarget> ResolveTargets(FrontierEntry entry, string currentScene, IResolutionTracer? tracer = null)
    {
        var results = new List<ResolvedTarget>();
        ResolveEntry(entry, currentScene, results, new HashSet<int>(), new HashSet<int>(), tracer);
        return results;
    }

    public IReadOnlyList<ResolvedTarget> ResolveUnlockTargets(int targetNodeId, FrontierEntry entry, string currentScene, IResolutionTracer? tracer = null)
    {
        var results = new List<ResolvedTarget>();
        ResolveUnlockRequirements(targetNodeId, entry, currentScene, results, new HashSet<int>(), new HashSet<int>(), tracer);
        return results;
    }


    private void ResolveEntry(
        FrontierEntry entry,
        string currentScene,
        List<ResolvedTarget> results,
        HashSet<int> questTrail,
        HashSet<int> itemTrail,
        IResolutionTracer? tracer = null)
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
                            ResolveItemRequirement(
                                giverId,
                                entry,
                                currentScene,
                                results,
                                questTrail,
                                itemTrail,
                                (itemId, source) => BuildGiverSemantic(entry.QuestIndex, giverId),
                                tracer);
                            continue;
                        }

                        int giverQuestIndex = _guide.FindQuestIndex(giverId);
                        if (giverNode.Type == NodeType.Quest && giverQuestIndex >= 0 && !_phases.IsCompleted(giverQuestIndex))
                        {
                            ResolveQuestFrontier(giverQuestIndex, entry.QuestIndex, currentScene, results, questTrail, itemTrail, tracer);
                            continue;
                        }

                        EmitNodePosition(
                            giverId,
                            giverId,
                            ResolvedTargetRole.Giver,
                            BuildGiverSemantic(entry.QuestIndex, giverId),
                            entry,
                            results,
                            tracer);
                    }
                    break;

                case QuestPhase.Accepted:
                    bool emittedObjective = false;
                    foreach (var requirement in _guide.RequiredItems(entry.QuestIndex))
                    {
                        int itemIndex = _guide.FindItemIndex(requirement.ItemId);
                        if (itemIndex >= 0 && _phases.GetItemCount(itemIndex) >= requirement.Quantity)
                            continue;

                        emittedObjective = true;
                        ResolveItemRequirement(
                            requirement.ItemId,
                            entry,
                            currentScene,
                            results,
                            questTrail,
                            itemTrail,
                            BuildSourceSemantic,
                            tracer);
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
                            tracer);
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
                                tracer);
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

    private void ResolveQuestFrontier(
        int questIndex,
        int requiredForQuestIndex,
        string currentScene,
        List<ResolvedTarget> results,
        HashSet<int> questTrail,
        HashSet<int> itemTrail,
        IResolutionTracer? tracer = null)
    {
        var frontier = new List<FrontierEntry>();
        new EffectiveFrontier(_guide, _phases).Resolve(questIndex, frontier, requiredForQuestIndex, tracer);
        for (int i = 0; i < frontier.Count; i++)
            ResolveEntry(frontier[i], currentScene, results, questTrail, itemTrail, tracer);
    }

    private void ResolveItemRequirement(
        int itemNodeId,
        FrontierEntry entry,
        string currentScene,
        List<ResolvedTarget> results,
        HashSet<int> questTrail,
        HashSet<int> itemTrail,
        Func<int, SourceSiteEntry, ResolvedActionSemantic> semanticFactory,
        IResolutionTracer? tracer = null)
    {
        if (!itemTrail.Add(itemNodeId))
            return;

        try
        {
            int itemIndex = _guide.FindItemIndex(itemNodeId);
            if (itemIndex >= 0)
            {
                foreach (var source in GetVisibleItemSources(itemIndex, tracer))
                {
                    ResolveItemSource(
                        itemNodeId,
                        source,
                        semanticFactory(itemNodeId, source),
                        entry,
                        currentScene,
                        results,
                        questTrail,
                        itemTrail,
                        tracer);
                }
            }

            foreach (var rewardEdge in _guide.InEdges(_guide.GetNodeKey(itemNodeId), EdgeType.RewardsItem))
            {
                if (!_guide.TryGetNodeId(rewardEdge.Source, out int rewardQuestId))
                    continue;

                int rewardQuestIndex = _guide.FindQuestIndex(rewardQuestId);
                if (rewardQuestIndex < 0 || _phases.IsCompleted(rewardQuestIndex))
                    continue;

                ResolveQuestFrontier(rewardQuestIndex, entry.QuestIndex, currentScene, results, questTrail, itemTrail, tracer);
            }
        }
        finally
        {
            itemTrail.Remove(itemNodeId);
        }
    }

    private void ResolveItemSource(
        int itemNodeId,
        SourceSiteEntry source,
        ResolvedActionSemantic semantic,
        FrontierEntry entry,
        string currentScene,
        List<ResolvedTarget> results,
        HashSet<int> questTrail,
        HashSet<int> itemTrail,
        IResolutionTracer? tracer = null)
    {
        var sourceNode = _guide.GetNode(source.SourceId);
        if (sourceNode.Type == NodeType.Recipe && source.EdgeType == EdgeProduces)
        {
            ResolveRecipeMaterials(source.SourceId, entry, currentScene, results, questTrail, itemTrail, tracer);
            return;
        }

        if (ResolveUnlockRequirements(source.SourceId, entry, currentScene, results, questTrail, itemTrail, tracer))
            return;

        var role = semantic.GoalKind == NavigationGoalKind.StartQuest
            ? ResolvedTargetRole.Giver
            : ResolvedTargetRole.Objective;
        EmitSourceTargets(source, role, semantic, entry, results, tracer);
    }

    private void ResolveUnlockCondition(
        UnlockConditionEntry condition,
        FrontierEntry entry,
        string currentScene,
        List<ResolvedTarget> results,
        HashSet<int> questTrail,
        HashSet<int> itemTrail,
        IResolutionTracer? tracer = null)
    {
        if (condition.CheckType == 0)
        {
            int questIndex = _guide.FindQuestIndex(condition.SourceId);
            if (questIndex >= 0 && !_phases.IsCompleted(questIndex))
                ResolveQuestFrontier(questIndex, entry.QuestIndex, currentScene, results, questTrail, itemTrail, tracer);
            return;
        }

        ResolveItemRequirement(
            condition.SourceId,
            entry,
            currentScene,
            results,
            questTrail,
            itemTrail,
            BuildSourceSemantic,
            tracer);
    }

    private bool ResolveUnlockRequirements(
        int targetNodeId,
        FrontierEntry entry,
        string currentScene,
        List<ResolvedTarget> results,
        HashSet<int> questTrail,
        HashSet<int> itemTrail,
        IResolutionTracer? tracer = null)
    {
        var groups = _unlocks.GetBlockingRequirementGroups(targetNodeId);
        if (groups.Count == 0)
            return false;

        for (int groupIndex = 0; groupIndex < groups.Count; groupIndex++)
        {
            foreach (var condition in groups[groupIndex])
                ResolveUnlockCondition(condition, entry, currentScene, results, questTrail, itemTrail, tracer);
        }
        return true;
    }

    private void ResolveRecipeMaterials(
        int recipeNodeId,
        FrontierEntry entry,
        string currentScene,
        List<ResolvedTarget> results,
        HashSet<int> questTrail,
        HashSet<int> itemTrail,
        IResolutionTracer? tracer = null)
    {
        foreach (var materialEdge in _guide.OutEdges(_guide.GetNodeKey(recipeNodeId), EdgeType.RequiresMaterial))
        {
            if (!_guide.TryGetNodeId(materialEdge.Target, out int materialId))
                continue;

            int materialIndex = _guide.FindItemIndex(materialId);
            if (materialIndex >= 0 && _phases.GetItemCount(materialIndex) >= (materialEdge.Quantity ?? 1))
                continue;

            ResolveItemRequirement(
                materialId,
                entry,
                currentScene,
                results,
                questTrail,
                itemTrail,
                BuildSourceSemantic,
                tracer);
        }
    }

    private void EmitNodePosition(
        int targetNodeId,
        int positionNodeId,
        ResolvedTargetRole role,
        ResolvedActionSemantic semantic,
        FrontierEntry entry,
        List<ResolvedTarget> results,
        IResolutionTracer? tracer = null)
    {
        if (_unlocks.Evaluate(targetNodeId, tracer) == UnlockResult.Blocked)
            return;

        var node = _guide.GetNode(positionNodeId);
        var scene = _guide.GetScene(positionNodeId);
        results.Add(new ResolvedTarget(
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
            entry.RequiredForQuestIndex));
        tracer?.OnTargetMaterialized(targetNodeId, positionNodeId, role.ToString(), scene, true);
    }

    private void EmitSourceTargets(
        SourceSiteEntry source,
        ResolvedTargetRole role,
        ResolvedActionSemantic semantic,
        FrontierEntry entry,
        List<ResolvedTarget> results,
        IResolutionTracer? tracer = null)
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
                tracer);
            return;
        }

        string? scene = _guide.GetSourceScene(source);
        foreach (var position in source.Positions)
        {
            WorldPosition? live = _livePositions.GetLivePosition(position.SpawnId);
            bool isActionable = _livePositions.IsAlive(position.SpawnId);
            results.Add(new ResolvedTarget(
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
                entry.RequiredForQuestIndex));
            tracer?.OnTargetMaterialized(source.SourceId, position.SpawnId, role.ToString(), scene, isActionable);
        }
    }

    private List<SourceSiteEntry> GetVisibleItemSources(int itemIndex, IResolutionTracer? tracer = null)
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
        QuestMarkerKind markerKind = repeatable ? QuestMarkerKind.QuestGiverRepeat : QuestMarkerKind.QuestGiver;

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
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(markerKind));
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
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(QuestMarkerKind.Objective));
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
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(QuestMarkerKind.Objective));
    }

    private ResolvedActionSemantic BuildTurnInSemantic(int questIndex, int completerId)
    {
        int questNodeId = _guide.QuestNodeId(questIndex);
        bool repeatable = _guide.GetNode(questNodeId).Repeatable;
        bool hasPayload = _guide.RequiredItems(questIndex).Length > 0;
        QuestMarkerKind markerKind = repeatable ? QuestMarkerKind.TurnInRepeatReady : QuestMarkerKind.TurnInReady;
        string? payload = hasPayload ? string.Join(", ", _guide.RequiredItems(questIndex).ToArray().Select(req => _guide.GetDisplayName(req.ItemId))) : null;
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
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(markerKind));
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
