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
    /// can verify (collect with inventory count). Non-verifiable steps (talk,
    /// kill, shout, turn_in) stop the pointer.
    ///
    /// Step 0 is auto-completed for active quests when it matches the
    /// acquisition action (talk to quest giver, read trigger item, enter zone).
    /// </summary>
    public static int GetCurrentStepIndex(QuestEntry quest, QuestStateTracker state)
    {
        if (quest.Steps == null || quest.Steps.Count == 0)
            return 0;

        if (state.IsCompleted(quest.DBName))
            return quest.Steps.Count;

        if (!state.IsActive(quest.DBName))
            return 0;

        int start = IsAcquisitionStep(quest, quest.Steps[0]) ? 1 : 0;

        for (int i = start; i < quest.Steps.Count; i++)
        {
            var step = quest.Steps[i];
            if (step.Action == "collect" && step.TargetName != null && step.Quantity.HasValue)
            {
                int have = state.CountItemInInventory(step.TargetName);
                if (have < step.Quantity.Value)
                    return i;
                // have >= need: this collect step is done, continue
            }
            else
            {
                // Can't verify: treat as current (conservative)
                return i;
            }
        }

        // All verifiable steps done — point to last step
        return quest.Steps.Count - 1;
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
            if (step.Action == "talk" && acq.Method == "dialog"
                && string.Equals(step.TargetName, acq.SourceName, System.StringComparison.OrdinalIgnoreCase))
                return true;

            if (step.Action == "read" && acq.Method == "item_read"
                && string.Equals(step.TargetName, acq.SourceName, System.StringComparison.OrdinalIgnoreCase))
                return true;

            if (step.Action == "travel" && acq.Method == "zone_entry")
                return true;
        }

        return false;
    }
}
