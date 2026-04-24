namespace AdventureGuide.Diagnostics;

internal readonly struct SnapshotEnvelope
{
    public SnapshotEnvelope(string name, object payload)
    {
        Name = name;
        Payload = payload;
    }

    public string Name { get; }
    public object Payload { get; }

    public static SnapshotEnvelope Create(string name, object payload)
    {
        return new SnapshotEnvelope(name, payload);
    }
}

internal readonly struct QuestCostSample
{
    public QuestCostSample(string questKey, long elapsedTicks)
    {
        QuestKey = questKey;
        ElapsedTicks = elapsedTicks;
    }

    public string QuestKey { get; }
    public long ElapsedTicks { get; }
}

internal sealed class MarkerDiagnosticsSnapshot
{
    public MarkerDiagnosticsSnapshot(int candidateCount, int entryCount, long lastProjectionTicks)
    {
        CandidateCount = candidateCount;
        EntryCount = entryCount;
        LastProjectionTicks = lastProjectionTicks;
    }

    public int CandidateCount { get; }
    public int EntryCount { get; }
    public long LastProjectionTicks { get; }
}

internal sealed class NavigationDiagnosticsSnapshot
{
    public NavigationDiagnosticsSnapshot(
        DiagnosticTrigger lastForceReason,
        int cacheEntryCount,
        string? currentTargetKey,
        int lastResolvedTargetCount,
        int lastBatchKeyCount,
        IReadOnlyList<QuestCostSample> topQuestCosts
    )
    {
        LastForceReason = lastForceReason;
        CacheEntryCount = cacheEntryCount;
        CurrentTargetKey = currentTargetKey;
        LastResolvedTargetCount = lastResolvedTargetCount;
        LastBatchKeyCount = lastBatchKeyCount;
        TopQuestCosts = topQuestCosts;
    }

    public DiagnosticTrigger LastForceReason { get; }
    public int CacheEntryCount { get; }
    public string? CurrentTargetKey { get; }
    public int LastResolvedTargetCount { get; }
    public int LastBatchKeyCount { get; }
    public IReadOnlyList<QuestCostSample> TopQuestCosts { get; }
}

internal sealed class TrackerDiagnosticsSnapshot
{
    public TrackerDiagnosticsSnapshot(
        int trackedQuestCount,
        string? lastResolveQuestKey,
        bool lastResolveUsedPreferredTarget,
        string? lastSummaryText
    )
    {
        TrackedQuestCount = trackedQuestCount;
        LastResolveQuestKey = lastResolveQuestKey;
        LastResolveUsedPreferredTarget = lastResolveUsedPreferredTarget;
        LastSummaryText = lastSummaryText;
    }

    public int TrackedQuestCount { get; }
    public string? LastResolveQuestKey { get; }
    public bool LastResolveUsedPreferredTarget { get; }
    public string? LastSummaryText { get; }
}

internal sealed class SpecTreeDiagnosticsSnapshot
{
    public SpecTreeDiagnosticsSnapshot(
        int lastProjectedNodeCount,
        int lastChildCount,
        int lastPrunedCount,
        int lastCyclePruneCount,
        int lastInvalidatedQuestCount,
        bool lastInvalidationWasFull,
        int lastViabilityEvaluationCount,
        int lastViabilityMemoHitCount,
        int lastMaxViabilityDepth
    )
    {
        LastProjectedNodeCount = lastProjectedNodeCount;
        LastChildCount = lastChildCount;
        LastPrunedCount = lastPrunedCount;
        LastCyclePruneCount = lastCyclePruneCount;
        LastInvalidatedQuestCount = lastInvalidatedQuestCount;
        LastInvalidationWasFull = lastInvalidationWasFull;
        LastViabilityEvaluationCount = lastViabilityEvaluationCount;
        LastViabilityMemoHitCount = lastViabilityMemoHitCount;
        LastMaxViabilityDepth = lastMaxViabilityDepth;
    }

    public int LastProjectedNodeCount { get; }
    public int LastChildCount { get; }
    public int LastPrunedCount { get; }
    public int LastCyclePruneCount { get; }
    public int LastInvalidatedQuestCount { get; }
    public bool LastInvalidationWasFull { get; }
    public int LastViabilityEvaluationCount { get; }
    public int LastViabilityMemoHitCount { get; }
    public int LastMaxViabilityDepth { get; }
}
