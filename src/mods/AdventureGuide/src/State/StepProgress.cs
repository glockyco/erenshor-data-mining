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

        if (quest.IsGuideOnly)
            return state.Workflows.GetCurrentStepIndex(quest, state.CountItemDelegate);

        if (state.IsCompleted(quest))
            return quest.Steps.Count;

        var steps = quest.Steps;
        bool actionable = state.IsActionable(quest);

        // Acquisition step is only auto-completed for active quests —
        // the player has already done it. For available quests, verify
        // all steps from the beginning.
        int start = actionable && IsAcquisitionStep(quest, steps[0]) ? 1 : 0;

        for (int i = start; i < steps.Count; )
        {
            var step = steps[i];
            if (step.RequirementVariant != null)
            {
                int end = i;
                while (end < steps.Count && steps[end].RequirementVariant != null)
                    end++;
                bool satisfied = false;
                for (int bundle = i; bundle < end; )
                {
                    string variant = steps[bundle].RequirementVariant!;
                    bool complete = true;
                    do
                    {
                        complete &= IsStepComplete(steps[bundle], state, data);
                        bundle++;
                    } while (bundle < end && steps[bundle].RequirementVariant == variant);
                    satisfied |= complete;
                }
                if (satisfied)
                {
                    i = end;
                    continue;
                }
                string firstVariant = step.RequirementVariant;
                while (
                    i < end
                    && steps[i].RequirementVariant == firstVariant
                    && IsStepComplete(steps[i], state, data)
                )
                    i++;
                return i;
            }
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

    internal static bool IsStepComplete(QuestStep step, QuestStateTracker state, GuideData data)
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
            return target != null && state.IsCompleted(target);
        }

        // Can't verify: treat as current (conservative).
        return false;
    }

    internal static bool HasRequiredItems(QuestEntry quest, Func<string, int> countItem)
    {
        if (quest.RequiredItems is not { Count: > 0 })
            return false;
        var missing = MissingRequirements(quest, countItem);
        return !missing.MoveNext();
    }

    internal static MissingRequirementEnumerator MissingRequirements(
        QuestEntry quest,
        Func<string, int> countItem
    ) => new(quest.RequiredItems, countItem);

    // Scan-local projection. A complete native bundle suppresses every native
    // alternative, but never suppresses independent AND or authored OR requirements.
    internal struct MissingRequirementEnumerator
    {
        private readonly List<RequiredItemInfo>? _items;
        private readonly Func<string, int> _countItem;
        private readonly bool _nativeSatisfied;
        private int _index;

        internal MissingRequirementEnumerator(
            List<RequiredItemInfo>? items,
            Func<string, int> countItem
        )
        {
            _items = items;
            _countItem = countItem;
            _nativeSatisfied = false;
            _index = -1;
            Current = null!;
            Have = 0;
            if (items == null)
                return;
            for (int i = 0; i < items.Count; i++)
            {
                string? variant = items[i].VariantKey;
                if (variant == null)
                    continue;
                bool seen = false;
                for (int previous = 0; previous < i; previous++)
                    if (items[previous].VariantKey == variant)
                    {
                        seen = true;
                        break;
                    }
                if (seen)
                    continue;
                bool complete = true;
                for (int member = i; member < items.Count; member++)
                    if (
                        items[member].VariantKey == variant
                        && countItem(items[member].ItemStableKey) < items[member].Quantity
                    )
                    {
                        complete = false;
                        break;
                    }
                if (complete)
                {
                    _nativeSatisfied = true;
                    break;
                }
            }
        }

        public MissingRequirementEnumerator GetEnumerator() => this;

        public RequiredItemInfo Current { get; private set; }
        public int Have { get; private set; }

        public bool MoveNext()
        {
            if (_items == null)
                return false;
            while (++_index < _items.Count)
            {
                var item = _items[_index];
                if (item.VariantKey != null && _nativeSatisfied)
                    continue;
                int have = _countItem(item.ItemStableKey);
                if (have >= item.Quantity)
                    continue;
                if (item.VariantKey == null && item.OrGroup != null)
                {
                    bool satisfied = false;
                    foreach (var alternative in _items)
                        if (
                            alternative.VariantKey == null
                            && alternative.OrGroup == item.OrGroup
                            && _countItem(alternative.ItemStableKey) >= alternative.Quantity
                        )
                        {
                            satisfied = true;
                            break;
                        }
                    if (satisfied)
                        continue;
                }
                Current = item;
                Have = have;
                return true;
            }
            return false;
        }
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
                if (state.IsCompleted(subQuest))
                    return (currentStep, currentQuest);

                int idx = GetCurrentStepIndex(subQuest, state, data);
                if (idx < 0 || idx >= subQuest.Steps.Count)
                    return (currentStep, currentQuest);

                currentStep = subQuest.Steps[idx];
                currentQuest = subQuest;
                continue;
            }

            // Pattern 2: collect step with quest_reward source → resolve
            // into the prerequisite quest if it's incomplete.
            if ((currentStep.Action is "collect" or "obtain") && currentStep.TargetName != null)
            {
                var subQuest = FindQuestRewardPrereq(currentQuest, currentStep, state, data);
                if (subQuest != null)
                {
                    int idx = GetCurrentStepIndex(subQuest, state, data);
                    if (idx >= 0 && idx < subQuest.Steps!.Count)
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
        var sources = ItemSourcePolicy.SourcesFor(quest, step);
        if (sources == null)
            return null;

        foreach (var src in sources)
        {
            if (src.Type != "quest_reward" || src.QuestKey == null)
                continue;
            var subQuest = data.GetByStableKey(src.QuestKey);
            if (subQuest?.Steps == null || subQuest.Steps.Count == 0)
                continue;
            if (state.IsCompleted(subQuest))
                continue;
            return subQuest;
        }

        return null;
    }
}
