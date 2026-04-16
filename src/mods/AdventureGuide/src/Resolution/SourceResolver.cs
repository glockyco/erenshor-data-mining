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

        switch (entry.Phase)
        {
            case QuestPhase.ReadyToAccept:
                foreach (int giverId in _guide.GiverIds(entry.QuestIndex))
                {
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
                    if (itemIndex < 0)
                    {
                        emittedObjective = true;
                        continue;
                    }
                    int count = _phases.GetItemCount(itemIndex);
                    if (count >= requirement.Quantity)
                        continue;

                    emittedObjective = true;
                    foreach (var source in GetVisibleItemSources(itemIndex, tracer))
                    {
                        if (_unlocks.Evaluate(source.SourceId, tracer) == UnlockResult.Blocked)
                            continue;

                        var semantic = BuildSourceSemantic(requirement.ItemId, source);
                        if (source.Positions.Length == 0)
                        {
                            EmitNodePosition(
                                source.SourceId,
                                source.SourceId,
                                ResolvedTargetRole.Objective,
                                semantic,
                                entry,
                                results,
                                tracer);
                            continue;
                        }

                        foreach (var position in source.Positions)
                        {
                            WorldPosition? live = _livePositions.GetLivePosition(position.SpawnId);
                            bool isActionable = _livePositions.IsAlive(position.SpawnId);
                            results.Add(new ResolvedTarget(
                                source.SourceId,
                                position.SpawnId,
                                ResolvedTargetRole.Objective,
                                semantic,
                                live?.X ?? position.X,
                                live?.Y ?? position.Y,
                                live?.Z ?? position.Z,
                                source.Scene,
                                live.HasValue,
                                isActionable,
                                entry.QuestIndex,
                                entry.RequiredForQuestIndex));
                            tracer?.OnTargetMaterialized(source.SourceId, position.SpawnId, nameof(ResolvedTargetRole.Objective), source.Scene, isActionable);
                        }
                    }
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

        _ = currentScene;
        return results;
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

        // Derive action from giver type: items/books are read, zones are entered, characters are talked to.
        var giverNode = _guide.GetNode(giverId);
        ResolvedActionKind actionKind = giverNode.Type switch
        {
            NodeType.Item or NodeType.Book => ResolvedActionKind.Read,
            NodeType.Zone                  => ResolvedActionKind.Travel,
            _                              => ResolvedActionKind.Talk,
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
            EdgeDropsItem  => ResolvedActionKind.Kill,
            EdgeSellsItem  => ResolvedActionKind.Buy,
            EdgeGivesItem  => ResolvedActionKind.Talk,
            EdgeYieldsItem => DetermineYieldAction(source.SourceType),
            EdgeContains   => ResolvedActionKind.Collect,
            EdgeProduces   => ResolvedActionKind.Collect,
            _              => ResolvedActionKind.Collect,
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
            zoneText: _guide.GetZoneDisplay(source.Scene),
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
            (byte)NodeType.Water      => ResolvedActionKind.Fish,
            _                         => ResolvedActionKind.Collect,
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
