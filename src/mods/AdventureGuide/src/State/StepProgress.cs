using AdventureGuide.Data;

namespace AdventureGuide.State;

/// <summary>
/// Determines the current step index for a quest based on game state.
/// Pure function of (quest data, tracker state) — no UI dependency.
///
/// Used by both QuestDetailPanel (to highlight the current step) and
/// NavigationController (to detect step completion for auto-advance).
/// </summary>
public static class StepProgress
{
    /// <summary>
    /// Returns the index of the first incomplete step, or Steps.Count if all
    /// verifiable steps are done. Conservative: only advances past steps we
    /// can verify. Non-verifiable steps (talk, kill, shout, turn_in) stop
    /// the pointer.
    ///
    /// Verifiable step types:
    ///   - collect: checks inventory count against required quantity
    ///   - complete_quest: checks whether the target quest is completed
    ///
    /// Step 0 is auto-completed for active quests when it matches the
    /// acquisition action (talk to quest giver, read trigger item, enter zone).
    /// For non-active quests, collect steps are still verified so the UI
    /// reflects actual inventory state.
    /// </summary>
    public static int GetCurrentStepIndex(QuestEntry quest, QuestStateTracker state, GuideData data)
    {
        if (quest.Steps == null || quest.Steps.Count == 0)
            return 0;

        if (state.IsCompleted(quest.DBName))
            return quest.Steps.Count;

        var steps = quest.Steps;
        bool actionable = state.IsActionable(quest.DBName);

        // Acquisition step is only auto-completed for active quests —
        // the player has already done it. For available quests, verify
        // all steps from the beginning.
        int start = actionable && IsAcquisitionStep(quest, steps[0]) ? 1 : 0;

        for (int i = start; i < steps.Count; )
        {
            var step = steps[i];
            string? group = step.OrGroup;
            if (group != null)
            {
                // Or-group alternatives are satisfied as a unit. A completed
                // alternative means the player chose that path, so skip all
                // members of the group as iteration proceeds.
                if (!IsOrGroupSatisfied(quest, steps, group, state, data, actionable))
                    return i;

                i++;
                while (
                    i < steps.Count
                    && string.Equals(steps[i].OrGroup, group, System.StringComparison.Ordinal)
                )
                    i++;
                continue;
            }

            if (!IsStepComplete(step, state, data))
                return i;

            i++;
        }

        // All verifiable steps done — point to last step
        return steps.Count - 1;
    }

    private static bool IsOrGroupSatisfied(
        QuestEntry quest,
        List<QuestStep> steps,
        string group,
        QuestStateTracker state,
        GuideData data,
        bool actionable
    )
    {
        for (int i = 0; i < steps.Count; i++)
        {
            var candidate = steps[i];
            if (!string.Equals(candidate.OrGroup, group, System.StringComparison.Ordinal))
                continue;

            // For an actionable quest, reaching any acquisition alternative
            // proves that the acquisition group has been satisfied.
            if (actionable && IsAcquisitionStep(quest, candidate))
                return true;

            if (IsStepComplete(candidate, state, data))
                return true;
        }

        return false;
    }

    private static bool IsStepComplete(QuestStep step, QuestStateTracker state, GuideData data)
    {
        if (
            string.Equals(step.Action, "collect", System.StringComparison.Ordinal)
            && step.TargetKey != null
            && step.Quantity.HasValue
        )
            return state.CountItem(step.TargetKey) >= step.Quantity.Value;

        if (
            string.Equals(step.Action, "complete_quest", System.StringComparison.Ordinal)
            && step.TargetKey != null
        )
        {
            // Resolve the target quest's DB name from its stable key
            // and check completion state.
            var target = data.GetByStableKey(step.TargetKey);
            return target != null && state.IsCompleted(target.DBName);
        }

        // Can't verify: treat as current (conservative).
        return false;
    }

    /// <summary>
    /// Returns true when step 0 represents the quest acquisition action
    /// itself (talk to quest giver, read trigger item, enter trigger zone).
    /// </summary>
    public static bool IsAcquisitionStep(QuestEntry quest, QuestStep step)
    {
        if (quest.Acquisition == null || quest.Acquisition.Count == 0)
            return false;

        foreach (var acq in quest.Acquisition)
        {
            if (
                step.Action == "talk"
                && acq.Method == "dialog"
                && string.Equals(
                    step.TargetName,
                    acq.SourceName,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
                return true;

            if (
                step.Action == "read"
                && acq.Method == "item_read"
                && string.Equals(
                    step.TargetName,
                    acq.SourceName,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
                return true;

            if (step.Action == "travel" && acq.Method == "zone_entry")
                return true;
        }

        return false;
    }

    /// <summary>
    /// Unwrap a step into the actual step the player should work on.
    /// Handles two patterns:
    ///   1. complete_quest steps → resolve into the sub-quest's current step
    ///   2. collect steps where the item comes from a quest_reward →
    ///      resolve into the prerequisite quest's current step
    /// Recurses through chains (depth-limited).
    ///
    /// Returns the resolved (step, quest) pair unchanged if no
    /// sub-quest resolution applies.
    /// </summary>
    public static (QuestStep? Step, QuestEntry? Quest) ResolveActiveStep(
        QuestStep step,
        QuestEntry quest,
        QuestStateTracker state,
        GuideData data,
        int maxDepth = 8
    )
    {
        var currentStep = step;
        var currentQuest = quest;

        for (int depth = 0; depth < maxDepth; depth++)
        {
            // Pattern 1: complete_quest → resolve sub-quest
            if (currentStep.Action == "complete_quest" && currentStep.TargetKey != null)
            {
                var subQuest = data.GetByStableKey(currentStep.TargetKey);
                if (subQuest?.Steps == null || subQuest.Steps.Count == 0)
                    return (currentStep, currentQuest);
                if (state.IsCompleted(subQuest.DBName))
                    return (currentStep, currentQuest);

                int idx = GetCurrentStepIndex(subQuest, state, data);
                if (idx >= subQuest.Steps.Count)
                    return (currentStep, currentQuest);

                currentStep = subQuest.Steps[idx];
                currentQuest = subQuest;
                continue;
            }

            // Pattern 2: collect step with quest_reward source → resolve
            // into the prerequisite quest if it's incomplete.
            if (currentStep.Action == "collect" && currentStep.TargetName != null)
            {
                var subQuest = FindQuestRewardPrereq(currentQuest, currentStep, state, data);
                if (subQuest != null)
                {
                    int idx = GetCurrentStepIndex(subQuest, state, data);
                    if (idx < subQuest.Steps!.Count)
                    {
                        currentStep = subQuest.Steps[idx];
                        currentQuest = subQuest;
                        continue;
                    }
                }
            }

            return (currentStep, currentQuest);
        }

        return (currentStep, currentQuest);
    }

    /// <summary>
    /// For a collect step, find an incomplete prerequisite quest if the
    /// item's source is a quest_reward. Returns null if no such prereq exists
    /// or the prereq is already completed.
    /// </summary>
    private static QuestEntry? FindQuestRewardPrereq(
        QuestEntry quest,
        QuestStep step,
        QuestStateTracker state,
        GuideData data
    )
    {
        if (quest.RequiredItems == null)
            return null;

        var item = quest.RequiredItems.Find(ri =>
            string.Equals(ri.ItemName, step.TargetName, System.StringComparison.OrdinalIgnoreCase)
        );
        if (item?.Sources == null)
            return null;

        foreach (var src in item.Sources)
        {
            if (src.Type != "quest_reward" || src.QuestKey == null)
                continue;
            var subQuest = data.GetByStableKey(src.QuestKey);
            if (subQuest?.Steps == null || subQuest.Steps.Count == 0)
                continue;
            if (state.IsCompleted(subQuest.DBName))
                continue;
            return subQuest;
        }

        return null;
    }
}
