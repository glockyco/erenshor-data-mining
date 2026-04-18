namespace AdventureGuide.Diagnostics;

internal enum DiagnosticEventKind
{
    QuestLogChanged,
    InventoryChanged,
    SceneChanged,
    NavSetChanged,
    TrackedQuestSetChanged,
    GuideChangeSetProduced,
    MarkerRebuildRequested,
    SelectorRefreshForced,
    IncidentTriggered,
}

internal enum DiagnosticSpanKind
{
    LiveStateUpdateFrame,
    MarkerApplyGuideChangeSet,
    MarkerRecompute,
    MarkerRebuildCurrentScene,
    MarkerCollectSceneQuestKeys,
    MarkerRebuildSceneQuestTargets,
    MarkerPublishMarkers,
    MarkerRebuildQuest,
    NavResolverResolve,
    NavSelectorTick,
    NavSelectorCollectKeys,
    NavSelectorBatchResolve,
    NavEngineUpdate,
    TrackerSummaryResolve,
    SpecTreeProjectRoot,
}

internal enum DiagnosticTrigger
{
    Unknown,
    SceneChanged,
    QuestLogChanged,
    InventoryChanged,
    LiveWorldChanged,
    NavSetChanged,
    TrackedQuestSetChanged,
    TargetSourceVersionChanged,
    ExplicitManualCapture,
    IncidentAutoCapture,
}

internal enum DiagnosticIncidentKind
{
    FrameHitch,
    FrameStall,
    RebuildStorm,
    ResolutionExplosion,
    ManualCapture,
}

internal enum MarkerRebuildMode
{
    Incremental,
    Full,
}

internal readonly struct DiagnosticEvent
{
    public DiagnosticEvent(
        DiagnosticEventKind kind,
        DiagnosticsContext context,
        long timestampTicks,
        string? primaryKey,
        int value0,
        int value1
    )
    {
        Kind = kind;
        Context = context;
        TimestampTicks = timestampTicks;
        PrimaryKey = primaryKey;
        Value0 = value0;
        Value1 = value1;
    }

    public DiagnosticEventKind Kind { get; }

    public DiagnosticsContext Context { get; }

    public long TimestampTicks { get; }

    public string? PrimaryKey { get; }

    public int Value0 { get; }

    public int Value1 { get; }
}

internal readonly struct DiagnosticSpan
{
    public DiagnosticSpan(
        DiagnosticSpanKind kind,
        DiagnosticsContext context,
        long startTicks,
        long endTicks,
        string? primaryKey,
        int value0,
        int value1
    )
    {
        Kind = kind;
        Context = context;
        StartTicks = startTicks;
        EndTicks = endTicks;
        PrimaryKey = primaryKey;
        Value0 = value0;
        Value1 = value1;
    }

    public DiagnosticSpanKind Kind { get; }

    public DiagnosticsContext Context { get; }

    public long StartTicks { get; }

    public long EndTicks { get; }

    public long ElapsedTicks => EndTicks - StartTicks;

    public string? PrimaryKey { get; }

    public int Value0 { get; }

    public int Value1 { get; }
}

internal readonly struct SpanToken
{
    public SpanToken(
        int id,
        DiagnosticSpanKind kind,
        DiagnosticsContext context,
        long startTicks,
        string? primaryKey
    )
    {
        Id = id;
        Kind = kind;
        Context = context;
        StartTicks = startTicks;
        PrimaryKey = primaryKey;
    }

    public int Id { get; }

    public DiagnosticSpanKind Kind { get; }

    public DiagnosticsContext Context { get; }

    public long StartTicks { get; }

    public string? PrimaryKey { get; }
}

internal sealed class IncidentThresholds
{
    public static IncidentThresholds Disabled { get; } =
        new(long.MaxValue, long.MaxValue, int.MaxValue, long.MaxValue, int.MaxValue);

    public IncidentThresholds(
        long frameHitchTicks,
        long frameStallTicks,
        int rebuildStormCount,
        long rebuildStormWindowTicks,
        int resolutionExplosionTargetCount
    )
    {
        FrameHitchTicks = frameHitchTicks;
        FrameStallTicks = frameStallTicks;
        RebuildStormCount = rebuildStormCount;
        RebuildStormWindowTicks = rebuildStormWindowTicks;
        ResolutionExplosionTargetCount = resolutionExplosionTargetCount;
    }

    public long FrameHitchTicks { get; }

    public long FrameStallTicks { get; }

    public int RebuildStormCount { get; }

    public long RebuildStormWindowTicks { get; }

    public int ResolutionExplosionTargetCount { get; }
}

internal sealed class DiagnosticIncident
{
    public DiagnosticIncident(
        DiagnosticIncidentKind kind,
        long timestampTicks,
        string? summary = null,
        DiagnosticSpanKind? triggerSpanKind = null,
        string? triggerPrimaryKey = null,
        long triggerElapsedTicks = 0,
        long thresholdTicks = 0,
        int correlationId = 0,
        int parentSpanId = 0
    )
    {
        Kind = kind;
        TimestampTicks = timestampTicks;
        Summary = summary;
        TriggerSpanKind = triggerSpanKind;
        TriggerPrimaryKey = triggerPrimaryKey;
        TriggerElapsedTicks = triggerElapsedTicks;
        ThresholdTicks = thresholdTicks;
        CorrelationId = correlationId;
        ParentSpanId = parentSpanId;
    }

    public DiagnosticIncidentKind Kind { get; }

    public long TimestampTicks { get; }

    public string? Summary { get; }

    public DiagnosticSpanKind? TriggerSpanKind { get; }

    public string? TriggerPrimaryKey { get; }

    public long TriggerElapsedTicks { get; }

    public long ThresholdTicks { get; }

    public int CorrelationId { get; }

    public int ParentSpanId { get; }

    public static DiagnosticIncident CreateForTests(
        DiagnosticIncidentKind kind,
        long timestampTicks
    )
    {
        return new DiagnosticIncident(kind, timestampTicks);
    }
}
