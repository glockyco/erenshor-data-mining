using AdventureGuide.CompiledGuide;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Resolution;

namespace AdventureGuide.UI.Tree;

internal sealed class DetailTreeViabilityEvaluator
{
    private const byte EdgeRewardsItem = (byte)EdgeType.RewardsItem;

    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestResolutionRecord _record;
    private readonly Dictionary<ViabilityCacheKey, DetailViabilityResult> _memo = new();

    public DetailTreeViabilityEvaluator(
        CompiledGuide.CompiledGuide guide,
        QuestResolutionRecord record
    )
    {
        _guide = guide;
        _record = record;
    }

    public int EvaluationCount { get; private set; }
    public int MemoHitCount { get; private set; }
    public int MaxDepth { get; private set; }

    public DetailViabilityResult Evaluate(DetailGoal goal, DetailBranchContext context)
    {
        var key = new ViabilityCacheKey(
            goal.Kind,
            goal.NodeId,
            goal.GroupId,
            context.ForbiddenFingerprint,
            context.BuildExactKey()
        );
        if (_memo.TryGetValue(key, out var cached))
        {
            MemoHitCount++;
            return cached;
        }

        EvaluationCount++;
        if (context.Ancestry.Count + 1 > MaxDepth)
            MaxDepth = context.Ancestry.Count + 1;

        DetailViabilityResult result;
        if (!IsAlreadySatisfied(goal) && context.ContainsBeforeCurrent(goal.NodeId))
            result = DetailViabilityResult.Pruned(DetailPruneReason.AncestorCycle);
        else
        {
            var next = context.Append(goal.NodeId);
            result = goal.Kind switch
            {
                DetailGoalKind.AcquireItem => EvaluateAcquireItem(goal.NodeId, next),
                DetailGoalKind.CompleteQuest => EvaluateCompleteQuest(goal.NodeId, next),
                DetailGoalKind.UnlockSource => EvaluateUnlockSource(goal.NodeId, next),
                DetailGoalKind.UseItemAction => EvaluateUseItemAction(goal.NodeId, next),
                DetailGoalKind.SatisfyUnlockGroup => EvaluateUnlockSource(goal.NodeId, next),
                _ => DetailViabilityResult.Pruned(DetailPruneReason.EmptySemanticGoal),
            };
        }

        _memo[key] = result;
        return result;
    }

    private DetailViabilityResult EvaluateAcquireItem(int itemNodeId, DetailBranchContext context)
    {
        int itemIndex = _guide.FindItemIndex(itemNodeId);
        if (itemIndex < 0)
            return DetailViabilityResult.Pruned(DetailPruneReason.NoAcquisitionSource);

        var surviving = new List<DetailGoal>();
        foreach (var source in _guide.GetItemSources(itemIndex))
        {
            var sourceGoal = new DetailGoal(DetailGoalKind.UnlockSource, source.SourceId);
            if (Evaluate(sourceGoal, context).IsViable)
                surviving.Add(sourceGoal);
        }

        foreach (
            var rewardEdge in _guide.InEdges(_guide.GetNodeKey(itemNodeId), EdgeType.RewardsItem)
        )
        {
            if (!_guide.TryGetNodeId(rewardEdge.Source, out int rewardQuestId))
                continue;
            var questGoal = new DetailGoal(DetailGoalKind.CompleteQuest, rewardQuestId);
            if (Evaluate(questGoal, context).IsViable)
                surviving.Add(questGoal);
        }

        return surviving.Count > 0
            ? DetailViabilityResult.Viable(surviving)
            : DetailViabilityResult.Pruned(DetailPruneReason.NoAcquisitionSource);
    }

    private DetailViabilityResult EvaluateCompleteQuest(
        int questNodeId,
        DetailBranchContext context
    )
    {
        int questIndex = _guide.FindQuestIndex(questNodeId);
        if (questIndex < 0)
            return DetailViabilityResult.Pruned(DetailPruneReason.EmptySemanticGoal);
        if (_record.DetailState.IsQuestCompleted(questIndex))
            return DetailViabilityResult.Viable(Array.Empty<DetailGoal>());

        var surviving = new List<DetailGoal>();

        foreach (int prereqId in _guide.PrereqQuestIds(questIndex))
        {
            var prereqGoal = new DetailGoal(DetailGoalKind.CompleteQuest, prereqId);
            var result = Evaluate(prereqGoal, context);
            if (!result.IsViable)
                return DetailViabilityResult.Pruned(DetailPruneReason.RequiredChildPruned);
            surviving.Add(prereqGoal);
        }

        var phase = _record.DetailState.GetPhase(questIndex);
        if (phase is not QuestPhase.Accepted and not QuestPhase.Completed)
        {
            var giverGoals = BuildGoals(_guide.GiverIds(questIndex), DetermineActionGoalKind)
                .ToArray();
            if (giverGoals.Length > 0)
            {
                var viableGiver = FirstViable(giverGoals, context);
                if (viableGiver is null)
                    return DetailViabilityResult.Pruned(DetailPruneReason.RequiredChildPruned);
                surviving.Add(viableGiver.Value);
            }
        }

        foreach (var requirement in _guide.RequiredItems(questIndex))
        {
            var itemGoal = new DetailGoal(DetailGoalKind.AcquireItem, requirement.ItemId);
            var result = Evaluate(itemGoal, context);
            if (!result.IsViable)
                return DetailViabilityResult.Pruned(DetailPruneReason.RequiredChildPruned);
            surviving.Add(itemGoal);
        }

        foreach (var step in _guide.Steps(questIndex))
        {
            var stepGoal = new DetailGoal(DetailGoalKind.UnlockSource, step.TargetId);
            var result = Evaluate(stepGoal, context);
            if (!result.IsViable)
                return DetailViabilityResult.Pruned(DetailPruneReason.RequiredChildPruned);
            surviving.Add(stepGoal);
        }

        var completerGoals = BuildGoals(_guide.CompleterIds(questIndex), DetermineActionGoalKind)
            .ToArray();
        if (completerGoals.Length > 0)
        {
            var viableCompleter = FirstViable(completerGoals, context);
            if (viableCompleter is null)
                return DetailViabilityResult.Pruned(DetailPruneReason.NoCompleterPath);
            surviving.Add(viableCompleter.Value);
        }

        return surviving.Count > 0
            ? DetailViabilityResult.Viable(surviving)
            : DetailViabilityResult.Pruned(DetailPruneReason.EmptySemanticGoal);
    }

    private DetailViabilityResult EvaluateUnlockSource(
        int sourceNodeId,
        DetailBranchContext context
    )
    {
        var groups = _record.DetailState.GetBlockingRequirementGroups(_guide, sourceNodeId);
        if (groups.Count == 0)
            return DetailViabilityResult.Viable(Array.Empty<DetailGoal>());

        var surviving = new List<DetailGoal>();
        for (int i = 0; i < groups.Count; i++)
        {
            if (TryEvaluateAllOfGroup(groups[i], context, out var groupChildren))
                surviving.AddRange(groupChildren);
        }

        return surviving.Count > 0
            ? DetailViabilityResult.Viable(surviving)
            : DetailViabilityResult.Pruned(DetailPruneReason.NoUnlockAlternative);
    }

    private DetailViabilityResult EvaluateUseItemAction(int itemNodeId, DetailBranchContext context)
    {
        int questIndex = FindItemActionQuestIndex(itemNodeId);
        if (questIndex >= 0 && _record.DetailState.IsQuestCompleted(questIndex))
            return DetailViabilityResult.Viable(Array.Empty<DetailGoal>());

        var acquireGoal = new DetailGoal(DetailGoalKind.AcquireItem, itemNodeId);
        var result = Evaluate(acquireGoal, context);
        return result.IsViable
            ? DetailViabilityResult.Viable(new[] { acquireGoal })
            : DetailViabilityResult.Pruned(DetailPruneReason.NoAcquisitionSource);
    }

    private bool TryEvaluateAllOfGroup(
        IReadOnlyList<UnlockConditionEntry> conditions,
        DetailBranchContext context,
        out DetailGoal[] surviving
    )
    {
        var goals = new List<DetailGoal>(conditions.Count);
        for (int i = 0; i < conditions.Count; i++)
        {
            var goal = BuildUnlockConditionGoal(conditions[i]);
            var result = Evaluate(goal, context);
            if (!result.IsViable)
            {
                surviving = Array.Empty<DetailGoal>();
                return false;
            }
            goals.Add(goal);
        }

        surviving = goals.ToArray();
        return surviving.Length > 0;
    }

    private DetailGoal BuildUnlockConditionGoal(UnlockConditionEntry condition)
    {
        if (condition.CheckType != 0 && _guide.FindItemIndex(condition.SourceId) >= 0)
            return new DetailGoal(DetailGoalKind.AcquireItem, condition.SourceId);

        var node = _guide.GetNode(condition.SourceId);
        return node.Type == NodeType.Quest
            ? new DetailGoal(DetailGoalKind.CompleteQuest, condition.SourceId)
            : new DetailGoal(DetailGoalKind.UnlockSource, condition.SourceId);
    }

    private DetailGoalKind DetermineActionGoalKind(int nodeId)
    {
        var node = _guide.GetNode(nodeId);
        return node.Type is NodeType.Item or NodeType.Book ? DetailGoalKind.UseItemAction
            : node.Type == NodeType.Quest ? DetailGoalKind.CompleteQuest
            : DetailGoalKind.UnlockSource;
    }

    private DetailGoal? FirstViable(IEnumerable<DetailGoal> goals, DetailBranchContext context)
    {
        foreach (var goal in goals)
        {
            if (Evaluate(goal, context).IsViable)
                return goal;
        }

        return null;
    }

    private DetailGoal[] BuildGoals(
        ReadOnlySpan<int> nodeIds,
        Func<int, DetailGoalKind> determineKind
    )
    {
        var goals = new DetailGoal[nodeIds.Length];
        for (int i = 0; i < nodeIds.Length; i++)
            goals[i] = new DetailGoal(determineKind(nodeIds[i]), nodeIds[i]);
        return goals;
    }

    private bool IsAlreadySatisfied(DetailGoal goal)
    {
        return goal.Kind switch
        {
            DetailGoalKind.CompleteQuest => IsQuestCompleted(goal.NodeId),
            DetailGoalKind.AcquireItem => HasItem(goal.NodeId),
            DetailGoalKind.UseItemAction => IsItemActionCompleted(goal.NodeId),
            _ => false,
        };
    }

    private bool IsQuestCompleted(int questNodeId)
    {
        int questIndex = _guide.FindQuestIndex(questNodeId);
        return questIndex >= 0 && _record.DetailState.IsQuestCompleted(questIndex);
    }

    private bool HasItem(int itemNodeId)
    {
        int itemIndex = _guide.FindItemIndex(itemNodeId);
        return itemIndex >= 0 && _record.DetailState.GetItemCount(itemIndex) > 0;
    }

    private bool IsItemActionCompleted(int itemNodeId)
    {
        int questIndex = FindItemActionQuestIndex(itemNodeId);
        return questIndex >= 0 && _record.DetailState.IsQuestCompleted(questIndex);
    }

    private int FindItemActionQuestIndex(int itemNodeId)
    {
        for (int questIndex = 0; questIndex < _guide.QuestCount; questIndex++)
        {
            foreach (int giverId in _guide.GiverIds(questIndex))
            {
                if (giverId == itemNodeId)
                    return questIndex;
            }

            foreach (int completerId in _guide.CompleterIds(questIndex))
            {
                if (completerId == itemNodeId)
                    return questIndex;
            }
        }

        return -1;
    }

    private readonly record struct ViabilityCacheKey(
        DetailGoalKind Kind,
        int NodeId,
        int? GroupId,
        ulong ForbiddenFingerprint,
        string ExactAncestry
    );
}
