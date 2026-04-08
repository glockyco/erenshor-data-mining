using AdventureGuide.CompiledGuide;

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

    public IReadOnlyList<ResolvedTarget> ResolveTargets(FrontierEntry entry, string currentScene)
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
                        results);
                }
                break;

            case QuestPhase.Accepted:
                bool emittedObjective = false;
                foreach (var requirement in _guide.RequiredItems(entry.QuestIndex))
                {
                    int itemIndex = FindItemIndex(requirement.ItemId);
                    int count = itemIndex >= 0 ? _phases.GetItemCount(itemIndex) : 0;
                    if (count >= requirement.Quantity || itemIndex < 0)
                        continue;

                    emittedObjective = true;
                    foreach (var source in GetVisibleItemSources(itemIndex))
                    {
                        if (_unlocks.Evaluate(source.SourceId) == UnlockResult.Blocked)
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
                                results);
                            continue;
                        }

                        foreach (var position in source.Positions)
                        {
                            WorldPosition? live = _livePositions.GetLivePosition(position.SpawnId);
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
                                _livePositions.IsAlive(position.SpawnId),
                                entry.QuestIndex,
                                entry.RequiredForQuestIndex));
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
                        results);
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
                            results);
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
        List<ResolvedTarget> results)
    {
        if (_unlocks.Evaluate(targetNodeId) == UnlockResult.Blocked)
            return;

        var node = _guide.GetNode(positionNodeId);
        results.Add(new ResolvedTarget(
            targetNodeId,
            positionNodeId,
            role,
            semantic,
            node.X,
            node.Y,
            node.Z,
            _guide.GetScene(positionNodeId),
            false,
            true,
            entry.QuestIndex,
            entry.RequiredForQuestIndex));
    }

    private int FindItemIndex(int itemNodeId)
    {
        for (int itemIndex = 0; itemIndex < _guide.ItemCount; itemIndex++)
        {
            if (_guide.ItemNodeId(itemIndex) == itemNodeId)
            {
                return itemIndex;
            }
        }

        return -1;
    }

    private List<SourceSiteEntry> GetVisibleItemSources(int itemIndex)
    {
        ReadOnlySpan<SourceSiteEntry> sources = _guide.GetItemSources(itemIndex);
        bool hasHostileDrop = false;
        for (int i = 0; i < sources.Length && !hasHostileDrop; i++)
        {
            if (sources[i].EdgeType == 16 && IsHostileDropSource(sources[i]))
                hasHostileDrop = true;
        }

        var visible = new List<SourceSiteEntry>(sources.Length);
        for (int i = 0; i < sources.Length; i++)
        {
            var source = sources[i];
            if (hasHostileDrop && source.EdgeType == 16 && !IsHostileDropSource(source))
                continue;
            visible.Add(source);
        }

        return visible;
    }

    private bool IsHostileDropSource(SourceSiteEntry source) =>
        ((NodeFlags)_guide.GetNode(source.SourceId).Flags & NodeFlags.IsFriendly) == 0;

    private ResolvedActionSemantic BuildGiverSemantic(int questIndex, int giverId)
    {
        int questNodeId = _guide.QuestNodeId(questIndex);
        bool repeatable = (_guide.GetNode(questNodeId).Flags & (ushort)NodeFlags.Repeatable) != 0;
        QuestMarkerKind markerKind = repeatable ? QuestMarkerKind.QuestGiverRepeat : QuestMarkerKind.QuestGiver;
        return new ResolvedActionSemantic(
            NavigationGoalKind.StartQuest,
            DetermineTargetKind(giverId),
            ResolvedActionKind.Talk,
            goalNodeKey: _guide.GetNodeKey(questNodeId),
            goalQuantity: null,
            keywordText: null,
            payloadText: null,
            targetIdentityText: _guide.GetDisplayName(giverId),
            contextText: _guide.GetDisplayName(questNodeId),
            rationaleText: null,
            zoneText: _guide.GetScene(giverId),
            availabilityText: null,
            preferredMarkerKind: markerKind,
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(markerKind));
    }

    private ResolvedActionSemantic BuildSourceSemantic(int itemNodeId, SourceSiteEntry source)
    {
        var actionKind = source.EdgeType switch
        {
            16 => ResolvedActionKind.Kill,   // DropsItem
            17 => ResolvedActionKind.Buy,    // SellsItem
            18 => ResolvedActionKind.Talk,   // GivesItem
            31 => DetermineYieldAction(source.SourceType), // YieldsItem
            29 => ResolvedActionKind.Collect, // Contains
            21 => ResolvedActionKind.Collect, // Produces
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
            zoneText: source.Scene,
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
            zoneText: _guide.GetScene(step.TargetId),
            availabilityText: null,
            preferredMarkerKind: QuestMarkerKind.Objective,
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(QuestMarkerKind.Objective));
    }

    private ResolvedActionSemantic BuildTurnInSemantic(int questIndex, int completerId)
    {
        int questNodeId = _guide.QuestNodeId(questIndex);
        bool repeatable = (_guide.GetNode(questNodeId).Flags & (ushort)NodeFlags.Repeatable) != 0;
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
            zoneText: _guide.GetScene(completerId),
            availabilityText: null,
            preferredMarkerKind: markerKind,
            markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(markerKind));
    }

    private static ResolvedActionKind DetermineYieldAction(byte sourceType) =>
        sourceType switch
        {
            6 => ResolvedActionKind.Mine,
            7 => ResolvedActionKind.Collect,
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
        byte nodeType = _guide.GetNode(nodeId).NodeType;
        return nodeType switch
        {
            2 => NavigationTargetKind.Character,
            1 => NavigationTargetKind.Item,
            0 => NavigationTargetKind.Quest,
            3 => NavigationTargetKind.Zone,
            4 => NavigationTargetKind.ZoneLine,
            _ => NavigationTargetKind.Object,
        };
    }
}
