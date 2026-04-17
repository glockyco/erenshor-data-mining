using AdventureGuide.CompiledGuide;
using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;

public enum UnlockResult
{
    Unlocked,
    Blocked,
}

public sealed class UnlockPredicateEvaluator
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;

    public UnlockPredicateEvaluator(CompiledGuide.CompiledGuide guide, QuestPhaseTracker phases)
    {
        _guide = guide;
        _phases = phases;
    }

    public UnlockResult Evaluate(int targetNodeId, IResolutionTracer? tracer = null)
    {
        UnlockResult result = GetBlockingRequirementGroups(targetNodeId).Count == 0
            ? UnlockResult.Unlocked
            : UnlockResult.Blocked;
        tracer?.OnUnlockEvaluation(targetNodeId, result == UnlockResult.Unlocked);
        return result;
    }

    public IReadOnlyList<IReadOnlyList<UnlockConditionEntry>> GetBlockingRequirementGroups(int targetNodeId)
    {
        if (!_guide.TryGetUnlockPredicate(targetNodeId, out var predicate))
            return Array.Empty<IReadOnlyList<UnlockConditionEntry>>();

        if (predicate.Semantics == 0)
        {
            var unmet = predicate.Conditions.Where(condition => !ConditionMet(condition)).ToArray();
            return unmet.Length == 0
                ? Array.Empty<IReadOnlyList<UnlockConditionEntry>>()
                : new IReadOnlyList<UnlockConditionEntry>[] { unmet };
        }

        var unconditional = predicate.Conditions
            .Where(condition => condition.Group == 0 && !ConditionMet(condition))
            .ToArray();
        var groups = new List<IReadOnlyList<UnlockConditionEntry>>();
        for (int group = 1; group <= predicate.GroupCount; group++)
        {
            bool hadConditions = false;
            var grouped = new List<UnlockConditionEntry>();
            foreach (var condition in predicate.Conditions)
            {
                if (condition.Group != group)
                    continue;

                hadConditions = true;
                if (!ConditionMet(condition))
                    grouped.Add(condition);
            }

            if (!hadConditions)
                continue;
            if (grouped.Count == 0 && unconditional.Length == 0)
                return Array.Empty<IReadOnlyList<UnlockConditionEntry>>();
            groups.Add(unconditional.Concat(grouped).ToArray());
        }

        if (groups.Count == 0 && unconditional.Length > 0)
            groups.Add(unconditional);
        return groups;
    }

    private bool ConditionMet(UnlockConditionEntry condition)
    {
        if (condition.CheckType == 0)
        {
            int questIndex = _guide.FindQuestIndex(condition.SourceId);
            return questIndex >= 0 && _phases.IsCompleted(questIndex);
        }

        int itemIndex = _guide.FindItemIndex(condition.SourceId);
        return itemIndex >= 0 && _phases.GetItemCount(itemIndex) > 0;
    }
}
