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

internal readonly struct MarkerRebuildModeSample
{
    public MarkerRebuildModeSample(MarkerRebuildMode mode, long timestampTicks)
    {
        Mode = mode;
        TimestampTicks = timestampTicks;
    }

    public MarkerRebuildMode Mode { get; }

    public long TimestampTicks { get; }
}

internal sealed class MarkerDiagnosticsSnapshot
{
    public MarkerDiagnosticsSnapshot(
        bool fullRebuild,
        int pendingQuestCount,
        DiagnosticTrigger lastReason,
        long lastDurationTicks,
        IReadOnlyList<QuestCostSample> topQuestCosts,
        IReadOnlyList<MarkerRebuildModeSample> recentModes
    )
    {
        FullRebuild = fullRebuild;
        PendingQuestCount = pendingQuestCount;
        LastReason = lastReason;
        LastDurationTicks = lastDurationTicks;
        TopQuestCosts = topQuestCosts;
        RecentModes = recentModes;
    }

    public bool FullRebuild { get; }

    public int PendingQuestCount { get; }

    public DiagnosticTrigger LastReason { get; }

    public long LastDurationTicks { get; }

    public IReadOnlyList<QuestCostSample> TopQuestCosts { get; }

    public IReadOnlyList<MarkerRebuildModeSample> RecentModes { get; }
}

internal sealed class NavigationDiagnosticsSnapshot
{
    public NavigationDiagnosticsSnapshot(
        DiagnosticTrigger lastForceReason,
        int cacheEntryCount,
        string? currentTargetKey,
        int lastResolvedTargetCount
    )
    {
        LastForceReason = lastForceReason;
        CacheEntryCount = cacheEntryCount;
        CurrentTargetKey = currentTargetKey;
        LastResolvedTargetCount = lastResolvedTargetCount;
    }

    public DiagnosticTrigger LastForceReason { get; }

    public int CacheEntryCount { get; }

    public string? CurrentTargetKey { get; }

    public int LastResolvedTargetCount { get; }
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
        int lastCyclePruneCount
    )
    {
        LastProjectedNodeCount = lastProjectedNodeCount;
        LastChildCount = lastChildCount;
        LastPrunedCount = lastPrunedCount;
        LastCyclePruneCount = lastCyclePruneCount;
    }

    public int LastProjectedNodeCount { get; }

    public int LastChildCount { get; }

    public int LastPrunedCount { get; }

    public int LastCyclePruneCount { get; }
}
