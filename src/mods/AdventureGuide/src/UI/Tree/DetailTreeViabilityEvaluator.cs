using AdventureGuide.CompiledGuide;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Resolution;

namespace AdventureGuide.UI.Tree;

internal sealed class DetailTreeViabilityEvaluator
{
    private readonly record struct DetailGoalKey(DetailGoalKind Kind, int NodeId);

    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestResolutionRecord _record;
    private readonly Dictionary<DetailGoalKey, DetailDependency[]> _compiledDependencies;
    private readonly Dictionary<ViabilityCacheKey, DetailViabilityResult> _memo = new();

    public DetailTreeViabilityEvaluator(
        CompiledGuide.CompiledGuide guide,
        QuestResolutionRecord record
    )
    {
        _guide = guide;
        _record = record;
        _compiledDependencies = BuildCompiledDependencies(guide);
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
        if (HasItem(itemNodeId))
            return DetailViabilityResult.Viable(Array.Empty<DetailGoal>());
        if (_guide.FindItemIndex(itemNodeId) < 0)
            return DetailViabilityResult.Pruned(DetailPruneReason.NoAcquisitionSource);

        var dependencies = GetCompiledDependencies(
            new DetailGoal(DetailGoalKind.AcquireItem, itemNodeId)
        );
        return dependencies.Length == 0
            ? DetailViabilityResult.Pruned(DetailPruneReason.NoAcquisitionSource)
            : EvaluateAnyAlternative(dependencies, context, DetailPruneReason.NoAcquisitionSource);
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

        var dependencies = GetCompiledDependencies(
            new DetailGoal(DetailGoalKind.CompleteQuest, questNodeId)
        );
        if (dependencies.Length == 0)
            return DetailViabilityResult.Pruned(DetailPruneReason.EmptySemanticGoal);

        var phase = _record.DetailState.GetPhase(questIndex);
        var surviving = new List<DetailGoal>();
        foreach (var dependency in dependencies)
        {
            if (
                phase is QuestPhase.Accepted or QuestPhase.Completed
                && IsQuestGiverDependency(questIndex, dependency)
            )
                continue;

            var result = EvaluateDependency(dependency, context);
            if (!result.IsViable)
            {
                return IsQuestCompleterDependency(questIndex, dependency)
                    ? DetailViabilityResult.Pruned(DetailPruneReason.NoCompleterPath)
                    : DetailViabilityResult.Pruned(DetailPruneReason.RequiredChildPruned);
            }

            surviving.AddRange(result.SurvivingChildren);
        }

        return DetailViabilityResult.Viable(surviving);
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

        var dependencies = GetCompiledDependencies(
            new DetailGoal(DetailGoalKind.UseItemAction, itemNodeId)
        );
        return dependencies.Length == 0
            ? DetailViabilityResult.Pruned(DetailPruneReason.NoAcquisitionSource)
            : EvaluateAllRequired(dependencies, context, DetailPruneReason.NoAcquisitionSource);
    }

    private DetailViabilityResult EvaluateAnyAlternative(
        IReadOnlyList<DetailDependency> dependencies,
        DetailBranchContext context,
        DetailPruneReason pruneReason
    )
    {
        var surviving = new List<DetailGoal>();
        for (int i = 0; i < dependencies.Count; i++)
        {
            var result = EvaluateDependency(dependencies[i], context);
            if (result.IsViable)
                surviving.AddRange(result.SurvivingChildren);
        }

        return surviving.Count > 0
            ? DetailViabilityResult.Viable(surviving)
            : DetailViabilityResult.Pruned(pruneReason);
    }

    private DetailViabilityResult EvaluateAllRequired(
        IReadOnlyList<DetailDependency> dependencies,
        DetailBranchContext context,
        DetailPruneReason pruneReason
    )
    {
        var surviving = new List<DetailGoal>();
        for (int i = 0; i < dependencies.Count; i++)
        {
            var result = EvaluateDependency(dependencies[i], context);
            if (!result.IsViable)
                return DetailViabilityResult.Pruned(pruneReason);
            surviving.AddRange(result.SurvivingChildren);
        }

        return DetailViabilityResult.Viable(surviving);
    }

    private DetailViabilityResult EvaluateDependency(
        DetailDependency dependency,
        DetailBranchContext context
    )
    {
        return dependency.Semantics switch
        {
            DetailDependencySemantics.AnyOf => EvaluateAnyOfDependency(dependency, context),
            DetailDependencySemantics.AllOf => EvaluateAllOfDependency(dependency, context),
            _ => DetailViabilityResult.Pruned(DetailPruneReason.EmptySemanticGoal),
        };
    }

    private DetailViabilityResult EvaluateAnyOfDependency(
        DetailDependency dependency,
        DetailBranchContext context
    )
    {
        for (int i = 0; i < dependency.Children.Length; i++)
        {
            var child = dependency.Children[i];
            if (Evaluate(child, context).IsViable)
                return DetailViabilityResult.Viable(new[] { child });
        }

        return DetailViabilityResult.Pruned(DetailPruneReason.RequiredChildPruned);
    }

    private DetailViabilityResult EvaluateAllOfDependency(
        DetailDependency dependency,
        DetailBranchContext context
    )
    {
        var surviving = new List<DetailGoal>(dependency.Children.Length);
        for (int i = 0; i < dependency.Children.Length; i++)
        {
            var child = dependency.Children[i];
            if (!Evaluate(child, context).IsViable)
                return DetailViabilityResult.Pruned(DetailPruneReason.RequiredChildPruned);
            surviving.Add(child);
        }

        return DetailViabilityResult.Viable(surviving);
    }

    private DetailDependency[] GetCompiledDependencies(DetailGoal goal)
    {
        var key = new DetailGoalKey(goal.Kind, goal.NodeId);
        if (_compiledDependencies.TryGetValue(key, out var dependencies))
        {
            if (dependencies.Length > 0 || !ShouldHaveCompiledDependencies(goal))
                return dependencies;
        }
        if (ShouldHaveCompiledDependencies(goal))
        {
            throw new InvalidOperationException(
                $"Compiled guide is missing detail dependencies for {goal.Kind} '{_guide.GetNodeKey(goal.NodeId)}'."
            );
        }

        return Array.Empty<DetailDependency>();
    }

    private bool ShouldHaveCompiledDependencies(DetailGoal goal)
    {
        return goal.Kind switch
        {
            DetailGoalKind.AcquireItem => _guide.FindItemIndex(goal.NodeId) >= 0,
            DetailGoalKind.CompleteQuest => QuestHasStaticDependencies(goal.NodeId),
            DetailGoalKind.UseItemAction => FindItemActionQuestIndex(goal.NodeId) >= 0,
            DetailGoalKind.UnlockSource => _guide.TryGetUnlockPredicate(
                goal.NodeId,
                out var predicate
            )
                && predicate.Conditions.Length > 0,
            _ => false,
        };
    }

    private bool QuestHasStaticDependencies(int questNodeId)
    {
        int questIndex = _guide.FindQuestIndex(questNodeId);
        return questIndex >= 0
            && (
                _guide.PrereqQuestIds(questIndex).Length > 0
                || _guide.RequiredItems(questIndex).Length > 0
                || _guide.Steps(questIndex).Length > 0
                || _guide.GiverIds(questIndex).Length > 0
                || _guide.CompleterIds(questIndex).Length > 0
            );
    }

    private static Dictionary<DetailGoalKey, DetailDependency[]> BuildCompiledDependencies(
        CompiledGuide.CompiledGuide guide
    )
    {
        var result = new Dictionary<DetailGoalKey, DetailDependency[]>();
        var goals = guide.DetailGoals;
        var dependencies = guide.DetailDependencies;
        for (int goalIndex = 0; goalIndex < goals.Length; goalIndex++)
        {
            var goal = goals[goalIndex];
            var clauses = new DetailDependency[goal.DependencyIndices.Length];
            for (
                int dependencyOffset = 0;
                dependencyOffset < goal.DependencyIndices.Length;
                dependencyOffset++
            )
            {
                int dependencyIndex = goal.DependencyIndices[dependencyOffset];
                if (dependencyIndex < 0 || dependencyIndex >= dependencies.Length)
                    throw new InvalidOperationException(
                        $"Invalid detail dependency index {dependencyIndex}."
                    );
                var dependency = dependencies[dependencyIndex];
                clauses[dependencyOffset] = new DetailDependency(
                    (DetailDependencySemantics)dependency.Semantics,
                    BuildChildGoals(goals, dependency),
                    dependency.UnlockGroup
                );
            }

            result[new DetailGoalKey((DetailGoalKind)goal.GoalKind, goal.NodeId)] = clauses;
        }

        return result;
    }

    private static DetailGoal[] BuildChildGoals(
        ReadOnlySpan<DetailGoalEntry> goals,
        DetailDependencyEntry dependency
    )
    {
        var children = new DetailGoal[dependency.ChildGoalIndices.Length];
        for (int i = 0; i < children.Length; i++)
        {
            int childGoalIndex = dependency.ChildGoalIndices[i];
            if (childGoalIndex < 0 || childGoalIndex >= goals.Length)
                throw new InvalidOperationException(
                    $"Invalid detail child goal index {childGoalIndex}."
                );
            var child = goals[childGoalIndex];
            children[i] = new DetailGoal((DetailGoalKind)child.GoalKind, child.NodeId);
        }

        return children;
    }

    private bool IsQuestGiverDependency(int questIndex, DetailDependency dependency) =>
        DependencyTargetsOnly(dependency, _guide.GiverIds(questIndex));

    private bool IsQuestCompleterDependency(int questIndex, DetailDependency dependency) =>
        DependencyTargetsOnly(dependency, _guide.CompleterIds(questIndex));

    private static bool DependencyTargetsOnly(
        DetailDependency dependency,
        ReadOnlySpan<int> nodeIds
    )
    {
        if (dependency.Children.Length == 0 || nodeIds.Length == 0)
            return false;
        for (int i = 0; i < dependency.Children.Length; i++)
        {
            if (!Contains(nodeIds, dependency.Children[i].NodeId))
                return false;
        }

        return true;
    }

    private static bool Contains(ReadOnlySpan<int> nodeIds, int nodeId)
    {
        for (int i = 0; i < nodeIds.Length; i++)
        {
            if (nodeIds[i] == nodeId)
                return true;
        }

        return false;
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
