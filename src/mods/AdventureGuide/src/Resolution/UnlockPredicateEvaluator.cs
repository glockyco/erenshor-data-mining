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
        UnlockResult result =
            GetBlockingRequirementGroups(targetNodeId).Count == 0
                ? UnlockResult.Unlocked
                : UnlockResult.Blocked;
        tracer?.OnUnlockEvaluation(targetNodeId, result == UnlockResult.Unlocked);
        return result;
    }

    public IReadOnlyList<IReadOnlyList<UnlockConditionEntry>> GetBlockingRequirementGroups(
        int targetNodeId
    )
    {
        if (!_guide.TryGetUnlockPredicate(targetNodeId, out var predicate))
            return Array.Empty<IReadOnlyList<UnlockConditionEntry>>();

        var conditions = predicate.Conditions;

        // Semantics == 0: flat predicate. Single group containing every unmet
        // condition; if all conditions are met, the target is unlocked.
        if (predicate.Semantics == 0)
        {
            int unmetCount = 0;
            for (int i = 0; i < conditions.Length; i++)
            {
                if (!ConditionMet(conditions[i]))
                    unmetCount++;
            }
            if (unmetCount == 0)
                return Array.Empty<IReadOnlyList<UnlockConditionEntry>>();

            var unmet = new UnlockConditionEntry[unmetCount];
            int w = 0;
            for (int i = 0; i < conditions.Length; i++)
            {
                if (!ConditionMet(conditions[i]))
                    unmet[w++] = conditions[i];
            }
            return new IReadOnlyList<UnlockConditionEntry>[] { unmet };
        }

        // Grouped predicate (Semantics != 0). Conditions with Group == 0 are
        // unconditional — they must be combined with each non-empty group. A
        // group with no conditions is ignored. If any group's conditions are all
        // met (after excluding the unconditional set, which is itself unmet), the
        // target is unlocked regardless of other groups.
        int unconditionalUnmetCount = 0;
        for (int i = 0; i < conditions.Length; i++)
        {
            if (conditions[i].Group == 0 && !ConditionMet(conditions[i]))
                unconditionalUnmetCount++;
        }
        UnlockConditionEntry[] unconditional;
        if (unconditionalUnmetCount == 0)
        {
            unconditional = Array.Empty<UnlockConditionEntry>();
        }
        else
        {
            unconditional = new UnlockConditionEntry[unconditionalUnmetCount];
            int w = 0;
            for (int i = 0; i < conditions.Length; i++)
            {
                if (conditions[i].Group == 0 && !ConditionMet(conditions[i]))
                    unconditional[w++] = conditions[i];
            }
        }

        var groups = new List<IReadOnlyList<UnlockConditionEntry>>();
        for (int group = 1; group <= predicate.GroupCount; group++)
        {
            bool hadConditions = false;
            int groupUnmetCount = 0;
            for (int i = 0; i < conditions.Length; i++)
            {
                if (conditions[i].Group != group)
                    continue;
                hadConditions = true;
                if (!ConditionMet(conditions[i]))
                    groupUnmetCount++;
            }

            if (!hadConditions)
                continue;

            // If this group is fully satisfied and the unconditional set is also
            // satisfied, the target is unlocked — blocking predicate is empty.
            if (groupUnmetCount == 0 && unconditional.Length == 0)
                return Array.Empty<IReadOnlyList<UnlockConditionEntry>>();

            int merged = unconditional.Length + groupUnmetCount;
            var combined = new UnlockConditionEntry[merged];
            int w = 0;
            for (int i = 0; i < unconditional.Length; i++)
                combined[w++] = unconditional[i];
            for (int i = 0; i < conditions.Length; i++)
            {
                if (conditions[i].Group == group && !ConditionMet(conditions[i]))
                    combined[w++] = conditions[i];
            }
            groups.Add(combined);
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
