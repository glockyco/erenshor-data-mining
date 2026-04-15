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

    public UnlockResult Evaluate(int targetNodeId)
    {
        if (!_guide.TryGetUnlockPredicate(targetNodeId, out var predicate))
        {
            return UnlockResult.Unlocked;
        }

        if (predicate.Semantics == 0)
        {
            return EvaluateAll(predicate);
        }

        return EvaluateAnyGroup(predicate);
    }

    private UnlockResult EvaluateAll(UnlockPredicateEntry predicate)
    {
        foreach (var condition in predicate.Conditions)
        {
            if (!ConditionMet(condition))
            {
                return UnlockResult.Blocked;
            }
        }

        return UnlockResult.Unlocked;
    }

    private UnlockResult EvaluateAnyGroup(UnlockPredicateEntry predicate)
    {
        foreach (var condition in predicate.Conditions)
        {
            if (condition.Group == 0 && !ConditionMet(condition))
            {
                return UnlockResult.Blocked;
            }
        }

        for (int group = 1; group <= predicate.GroupCount; group++)
        {
            bool passed = true;
            bool sawCondition = false;
            foreach (var condition in predicate.Conditions)
            {
                if (condition.Group != group)
                {
                    continue;
                }

                sawCondition = true;
                if (!ConditionMet(condition))
                {
                    passed = false;
                    break;
                }
            }

            if (sawCondition && passed)
            {
                return UnlockResult.Unlocked;
            }
        }

        return UnlockResult.Blocked;
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
