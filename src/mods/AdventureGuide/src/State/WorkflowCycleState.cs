using AdventureGuide.Data;

namespace AdventureGuide.State;

/// <summary>
/// Unity-free state machine for one guide-only repeatable workflow. The
/// GuideWorkflowState adapter supplies observed game evidence; this class owns
/// all transition, progress, reset, and recovery semantics.
/// </summary>
internal sealed class WorkflowCycleState
{
    private readonly Dictionary<string, int> _expectedByGroup = new(
        StringComparer.OrdinalIgnoreCase
    );
    private readonly Dictionary<string, int> _killedByGroup = new(StringComparer.OrdinalIgnoreCase);
    private readonly KillRequirement?[] _killRequirements;

    public QuestEntry Quest { get; }
    public WorkflowStage Stage { get; private set; }
    public int Generation { get; private set; }
    public int LastItemCount { get; private set; }
    public bool TriggerLatched { get; private set; }
    public bool RecoveryPending { get; private set; }
    public bool RewardSeen { get; private set; }

    private readonly struct KillRequirement
    {
        public readonly string Group;
        public readonly int Count;

        public KillRequirement(string group, int count)
        {
            Group = group;
            Count = count;
        }
    }

    public WorkflowCycleState(QuestEntry quest)
    {
        Quest = quest;
        var steps = quest.Steps ?? [];
        _killRequirements = new KillRequirement?[steps.Count];
        var cumulativeKills = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        for (int i = 0; i < steps.Count; i++)
        {
            var step = steps[i];
            if (step.Action != "kill" || step.TargetKey == null)
                continue;
            var group = CharacterStableKey.Normalize(step.TargetKey);
            int count = cumulativeKills.TryGetValue(group, out int prior)
                ? prior + (step.Quantity ?? 1)
                : step.Quantity ?? 1;
            cumulativeKills[group] = count;
            _killRequirements[i] = new KillRequirement(group, count);
        }

        foreach (var target in quest.WorkflowCycle!.Targets)
        {
            var group = CharacterStableKey.Normalize(target.StableKey);
            _expectedByGroup[group] = _expectedByGroup.TryGetValue(group, out int quantity)
                ? quantity + target.Quantity
                : target.Quantity;
        }
    }

    public void Restore(int generation, bool triggerLatched, int currentItemCount)
    {
        Generation = Math.Max(0, generation);
        TriggerLatched = triggerLatched;
        RecoveryPending = triggerLatched;
        RewardSeen = false;
        LastItemCount = currentItemCount;
        _killedByGroup.Clear();
        Stage = triggerLatched
            ? WorkflowStage.TriggerConsumed
            : StageForInventory(currentItemCount);
    }

    public bool BeginScene(int currentItemCount)
    {
        bool changed = LastItemCount != currentItemCount || RewardSeen;
        LastItemCount = currentItemCount;
        RewardSeen = false;
        RecoveryPending = TriggerLatched;
        changed |= SetStage(
            TriggerLatched ? WorkflowStage.TriggerConsumed : StageForInventory(currentItemCount)
        );
        return changed;
    }

    public bool ObserveInventory(int currentItemCount, bool insideTrigger)
    {
        int previous = LastItemCount;
        LastItemCount = currentItemCount;
        bool changed = previous != currentItemCount;
        bool consumed = previous - currentItemCount >= Quest.WorkflowCycle!.Trigger.Quantity;
        if (!TriggerLatched && consumed && insideTrigger)
        {
            TriggerLatched = true;
            RecoveryPending = false;
            return SetStage(WorkflowStage.TriggerConsumed) || changed;
        }

        if (!TriggerLatched)
            changed |= SetStage(StageForInventory(currentItemCount));
        return changed;
    }

    public bool RefreshInventory(int currentItemCount)
    {
        bool changed = LastItemCount != currentItemCount;
        LastItemCount = currentItemCount;
        if (!TriggerLatched && Stage != WorkflowStage.Unverifiable)
            changed |= SetStage(StageForInventory(currentItemCount));
        return changed;
    }

    public bool RecoverFromLiveTargets(int currentItemCount)
    {
        bool changed = !TriggerLatched || RecoveryPending || LastItemCount != currentItemCount;
        TriggerLatched = true;
        RecoveryPending = false;
        LastItemCount = currentItemCount;
        changed |= SetStage(WorkflowStage.TargetsActive);
        return changed;
    }

    public bool ObserveTarget()
    {
        bool changed = RecoveryPending;
        RecoveryPending = false;
        changed |= SetStage(WorkflowStage.TargetsActive);
        return changed;
    }

    public bool RecordTargetDeath(string group, bool anyLiveTargets)
    {
        _killedByGroup[group] = _killedByGroup.TryGetValue(group, out int killed) ? killed + 1 : 1;
        if (!TargetsDefeated)
        {
            SetStage(anyLiveTargets ? WorkflowStage.TargetsActive : WorkflowStage.TriggerConsumed);
        }
        return true;
    }

    public bool ObserveReward()
    {
        bool changed = !TriggerLatched || RecoveryPending || !RewardSeen;
        TriggerLatched = true;
        RecoveryPending = false;
        RewardSeen = true;
        foreach (var expected in _expectedByGroup)
            _killedByGroup[expected.Key] = expected.Value;
        changed |= SetStage(WorkflowStage.RewardAvailable);
        return changed;
    }

    public bool UpdatePresence(int liveTargetCount, bool lostObservedTarget)
    {
        if (lostObservedTarget)
            return MarkUnverifiable();
        if (RewardSeen)
            return SetStage(WorkflowStage.RewardAvailable);
        if (liveTargetCount > 0)
            return SetStage(WorkflowStage.TargetsActive);
        if (Stage != WorkflowStage.Unverifiable)
            return SetStage(WorkflowStage.TriggerConsumed);
        return false;
    }

    public bool CompleteRecovery(bool hasRuntimeEvidence)
    {
        if (!RecoveryPending)
            return false;
        RecoveryPending = false;
        return hasRuntimeEvidence ? false : MarkUnverifiable();
    }

    public bool MarkUnverifiable() => SetStage(WorkflowStage.Unverifiable);

    public void ResetCycle(int currentItemCount)
    {
        Generation++;
        Reset(currentItemCount);
    }

    public void Reset(int currentItemCount)
    {
        TriggerLatched = false;
        RecoveryPending = false;
        RewardSeen = false;
        _killedByGroup.Clear();
        LastItemCount = currentItemCount;
        Stage = StageForInventory(currentItemCount);
    }

    public int GetCurrentStepIndex(Func<string, int> countItem)
    {
        var steps = Quest.Steps;
        if (steps == null)
            return 0;
        if (Stage == WorkflowStage.Unverifiable)
            return -1;

        for (int i = 0; i < steps.Count; i++)
        {
            var step = steps[i];
            bool complete;
            switch (step.Action)
            {
                case "obtain":
                    complete =
                        TriggerLatched
                        || (
                            step.TargetKey != null
                            && countItem(step.TargetKey) >= (step.Quantity ?? 1)
                        );
                    break;
                case "go_to":
                    complete = TriggerLatched;
                    break;
                case "kill" when _killRequirements[i] is { } requirement:
                    complete =
                        _killedByGroup.TryGetValue(requirement.Group, out int killed)
                        && killed >= requirement.Count;
                    break;
                case "loot":
                    complete = false;
                    break;
                default:
                    complete = false;
                    break;
            }
            if (!complete)
                return i;
        }
        return steps.Count;
    }

    public bool TargetsDefeated
    {
        get
        {
            foreach (var expected in _expectedByGroup)
            {
                if (
                    !_killedByGroup.TryGetValue(expected.Key, out int killed)
                    || killed < expected.Value
                )
                    return false;
            }
            return true;
        }
    }

    public string TargetSignature =>
        string.Join(
            "|",
            _expectedByGroup.Keys.OrderBy(key => key, StringComparer.OrdinalIgnoreCase)
        );

    private WorkflowStage StageForInventory(int count) =>
        count >= Quest.WorkflowCycle!.Trigger.Quantity
            ? WorkflowStage.ItemReady
            : WorkflowStage.NeedItem;

    private bool SetStage(WorkflowStage stage)
    {
        if (Stage == stage)
            return false;
        Stage = stage;
        return true;
    }
}
