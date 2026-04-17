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
    MarkerRebuildQuest,
    NavResolverResolve,
    NavSelectorTick,
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
        new(long.MaxValue, int.MaxValue, long.MaxValue, int.MaxValue);

    public IncidentThresholds(
        long frameStallTicks,
        int rebuildStormCount,
        long rebuildStormWindowTicks,
        int resolutionExplosionTargetCount
    )
    {
        FrameStallTicks = frameStallTicks;
        RebuildStormCount = rebuildStormCount;
        RebuildStormWindowTicks = rebuildStormWindowTicks;
        ResolutionExplosionTargetCount = resolutionExplosionTargetCount;
    }

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
        string? summary = null
    )
    {
        Kind = kind;
        TimestampTicks = timestampTicks;
        Summary = summary;
    }

    public DiagnosticIncidentKind Kind { get; }

    public long TimestampTicks { get; }

    public string? Summary { get; }

    public static DiagnosticIncident CreateForTests(
        DiagnosticIncidentKind kind,
        long timestampTicks
    )
    {
        return new DiagnosticIncident(kind, timestampTicks);
    }
}
