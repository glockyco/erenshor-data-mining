using AdventureGuide.Plan;
using AdventureGuide.Position;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Resolution;

/// <summary>
/// Shared quest-resolution entry point for maintained views.
/// Owns scene-aware quest resolution records and exposes batched resolution.
/// </summary>
public sealed class QuestResolutionService
{
    private readonly CompiledGuideModel _guide;
    private readonly EffectiveFrontier _frontier;
    private readonly QuestTargetResolver _questTargetResolver;
    private readonly QuestTargetProjector _projector;
    private readonly GuideDependencyEngine? _dependencies;
    private readonly ZoneRouter? _zoneRouter;
    private readonly Func<int> _versionProvider;
    private readonly Func<SourceResolver.ResolutionSession> _sessionFactory;
    private readonly AdventureGuide.Diagnostics.DiagnosticsCore? _diagnostics;
    private readonly Dictionary<string, QuestResolutionRecord> _cache = new(StringComparer.Ordinal);
    // BuildBlockingZoneLineByScene is a function of (currentScene, phase-state).
    // Phase state only changes on version bumps, and every quest resolved within a
    // batch observes the same currentScene, so the result is identical across all
    // records in one (scene, version) snapshot. Cache and share.
    private readonly Dictionary<string, IReadOnlyDictionary<string, int>> _blockingZoneCache = new(StringComparer.OrdinalIgnoreCase);
    private int _lastBatchKeyCount;
    private int _lastObservedVersion = int.MinValue;
    private IReadOnlyList<AdventureGuide.Diagnostics.QuestCostSample> _topQuestCosts = Array.Empty<AdventureGuide.Diagnostics.QuestCostSample>();

    public QuestResolutionService(
        CompiledGuideModel guide,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver,
        ZoneRouter? zoneRouter,
        QuestTargetProjector projector,
        GuideDependencyEngine? dependencies = null,
        Func<int>? versionProvider = null
    ) : this(
        guide,
        frontier,
        sourceResolver,
        zoneRouter,
        projector,
        dependencies,
        versionProvider,
        sessionFactory: null,
        diagnostics: null
    ) { }

    internal QuestResolutionService(
        CompiledGuideModel guide,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver,
        ZoneRouter? zoneRouter,
        QuestTargetProjector projector,
        GuideDependencyEngine? dependencies,
        Func<int>? versionProvider,
        Func<SourceResolver.ResolutionSession>? sessionFactory,
        AdventureGuide.Diagnostics.DiagnosticsCore? diagnostics = null
    )
    {
        _guide = guide;
        _frontier = frontier;
        _projector = projector;
        _dependencies = dependencies;
        _zoneRouter = zoneRouter;
        _versionProvider = versionProvider ?? (() => 0);
        _sessionFactory = sessionFactory ?? (() => new SourceResolver.ResolutionSession());
        _diagnostics = diagnostics;
        _questTargetResolver = new QuestTargetResolver(
            guide,
            frontier,
            sourceResolver,
            zoneRouter
        );
    }

    public int Version => _versionProvider();

    public int LastBatchKeyCount => _lastBatchKeyCount;

    internal int CacheEntryCount => _cache.Count;

    internal IReadOnlyList<AdventureGuide.Diagnostics.QuestCostSample> TopQuestCosts => _topQuestCosts;

    private void EnsureVersionCurrent()
    {
        int version = _versionProvider();
        if (version == _lastObservedVersion)
            return;

        _cache.Clear();
        _blockingZoneCache.Clear();
        _lastObservedVersion = version;
    }

    public QuestResolutionRecord ResolveQuest(
        string questKey,
        string currentScene,
        IResolutionTracer? tracer = null
    ) => ResolveQuest(questKey, currentScene, session: null, tracer);

    internal QuestResolutionRecord ResolveQuest(
        string questKey,
        string currentScene,
        SourceResolver.ResolutionSession? session,
        IResolutionTracer? tracer = null
    )
    {
        EnsureVersionCurrent();
        SourceResolver.ResolutionSession? resolutionSession = session;
        var record = ResolveOrBuildRecord(questKey, currentScene, ref resolutionSession, tracer);
        if (record == null)
            throw new InvalidOperationException($"Quest '{questKey}' did not resolve.");

        _lastBatchKeyCount = 1;
        _topQuestCosts = Array.Empty<AdventureGuide.Diagnostics.QuestCostSample>();
        return record;
    }

    public IReadOnlyDictionary<string, QuestResolutionRecord> ResolveBatch(
        IEnumerable<string> questKeys,
        string currentScene,
        IResolutionTracer? tracer = null
    ) => ResolveBatch(questKeys, currentScene, session: null, tracer);

    internal IReadOnlyDictionary<string, QuestResolutionRecord> ResolveBatch(
        IEnumerable<string> questKeys,
        string currentScene,
        SourceResolver.ResolutionSession? session,
        IResolutionTracer? tracer = null
    )
    {
        EnsureVersionCurrent();
        var results = new Dictionary<string, QuestResolutionRecord>(StringComparer.Ordinal);
        SourceResolver.ResolutionSession? resolutionSession = session;
        var seenKeys = new HashSet<string>(StringComparer.Ordinal);
        var questCosts = new List<AdventureGuide.Diagnostics.QuestCostSample>();
        foreach (var questKey in questKeys)
        {
            if (string.IsNullOrWhiteSpace(questKey) || !seenKeys.Add(questKey))
                continue;

            long start = System.Diagnostics.Stopwatch.GetTimestamp();
            var record = ResolveOrBuildRecord(questKey, currentScene, ref resolutionSession, tracer);
            long elapsed = System.Diagnostics.Stopwatch.GetTimestamp() - start;
            questCosts.Add(new AdventureGuide.Diagnostics.QuestCostSample(questKey, elapsed));
            if (record != null)
                results[questKey] = record;
        }

        _lastBatchKeyCount = seenKeys.Count;
        questCosts.Sort((left, right) => right.ElapsedTicks.CompareTo(left.ElapsedTicks));
        if (questCosts.Count > 5)
            questCosts.RemoveRange(5, questCosts.Count - 5);
        _topQuestCosts = questCosts.Count == 0
            ? Array.Empty<AdventureGuide.Diagnostics.QuestCostSample>()
            : questCosts;
        return results;
    }

    public void InvalidateAffected(IReadOnlyCollection<GuideDerivedKey> affectedDerivedKeys)
    {
        EnsureVersionCurrent();
        foreach (var derivedKey in affectedDerivedKeys)
        {
            if (derivedKey.Kind == GuideDerivedKind.QuestTargets)
                _cache.Remove(derivedKey.Key);
        }
    }

    private QuestResolutionRecord? ResolveOrBuildRecord(
        string questKey,
        string currentScene,
        ref SourceResolver.ResolutionSession? session,
        IResolutionTracer? tracer
    )
    {
        string cacheKey = BuildCacheKey(questKey, currentScene);
        if (_cache.TryGetValue(cacheKey, out var cached))
            return cached;
        if (!_guide.TryGetNodeId(questKey, out int questNodeId))
            return null;

        int questIndex = _guide.FindQuestIndex(questNodeId);
        if (questIndex < 0)
            return null;

        var resolutionSession = session ??= _sessionFactory();
        QuestResolutionRecord record;
        if (_dependencies == null)
        {
            record = BuildRecord(questKey, currentScene, questIndex, resolutionSession, tracer);
        }
        else
        {
            using (_dependencies.BeginCollection(new GuideDerivedKey(GuideDerivedKind.QuestTargets, cacheKey)))
                record = BuildRecord(questKey, currentScene, questIndex, resolutionSession, tracer);
        }

        _cache[cacheKey] = record;
        return record;
    }

    private QuestResolutionRecord BuildRecord(
        string questKey,
        string currentScene,
        int questIndex,
        SourceResolver.ResolutionSession session,
        IResolutionTracer? tracer
    )
    {
        var token = _diagnostics?.BeginSpan(
            AdventureGuide.Diagnostics.DiagnosticSpanKind.MarkerServiceBuildRecord,
            AdventureGuide.Diagnostics.DiagnosticsContext.Root(AdventureGuide.Diagnostics.DiagnosticTrigger.Unknown),
            primaryKey: questKey
        );
        long startTick = System.Diagnostics.Stopwatch.GetTimestamp();
        try
        {
            var frontier = new List<FrontierEntry>();
            _frontier.Resolve(questIndex, frontier, -1, tracer);
            var compiledTargets = _questTargetResolver.Resolve(questIndex, currentScene, frontier, session, tracer);
            // Projection is deferred: markers and tracker-summary never read
            // NavigationTargets, so most records never pay the projection cost.
            var capturedTargets = compiledTargets;
            var capturedScene = currentScene;
            Func<IReadOnlyList<ResolvedQuestTarget>> navigationTargetsFactory =
                () => _projector.Project(capturedTargets, capturedScene);
            var phases = _frontier.Phases;
            var questPhases = phases.SnapshotPhases();
            var itemCounts = phases.SnapshotItemCounts();
            var blockingZoneLineByScene = BuildBlockingZoneLineByScene(currentScene);
            return new QuestResolutionRecord(
                questKey,
                currentScene,
                questIndex,
                frontier,
                compiledTargets,
                navigationTargetsFactory,
                questPhases,
                itemCounts,
                blockingZoneLineByScene
            );
        }
        finally
        {
            if (token != null)
                _diagnostics!.EndSpan(
                    token.Value,
                    System.Diagnostics.Stopwatch.GetTimestamp() - startTick
                );
        }
    }

    private IReadOnlyDictionary<string, int> BuildBlockingZoneLineByScene(string currentScene)
    {
        string sceneKey = currentScene ?? string.Empty;
        if (_blockingZoneCache.TryGetValue(sceneKey, out var cached))
            return cached;

        var token = _diagnostics?.BeginSpan(
            AdventureGuide.Diagnostics.DiagnosticSpanKind.MarkerServiceBuildBlockingZones,
            AdventureGuide.Diagnostics.DiagnosticsContext.Root(AdventureGuide.Diagnostics.DiagnosticTrigger.Unknown),
            primaryKey: currentScene
        );
        long startTick = System.Diagnostics.Stopwatch.GetTimestamp();
        int zonesScanned = 0;
        int blockedCount = 0;
        try
        {
            IReadOnlyDictionary<string, int> result;
            if (_zoneRouter == null || string.IsNullOrWhiteSpace(currentScene))
            {
                result = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            }
            else
            {
                var blockedByScene = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
                foreach (var zone in _guide.NodesOfType(Graph.NodeType.Zone))
                {
                    if (string.IsNullOrWhiteSpace(zone.Scene))
                        continue;
                    if (string.Equals(zone.Scene, currentScene, StringComparison.OrdinalIgnoreCase))
                        continue;

                    zonesScanned++;
                    var lockedHop = _zoneRouter.FindFirstLockedHop(currentScene, zone.Scene);
                    if (lockedHop == null)
                        continue;
                    if (_guide.TryGetNodeId(lockedHop.ZoneLineKey, out int zoneLineNodeId))
                    {
                        blockedByScene[zone.Scene] = zoneLineNodeId;
                        blockedCount++;
                    }
                }
                result = blockedByScene;
            }
            _blockingZoneCache[sceneKey] = result;
            return result;
        }
        finally
        {
            if (token != null)
                _diagnostics!.EndSpan(
                    token.Value,
                    System.Diagnostics.Stopwatch.GetTimestamp() - startTick,
                    value0: zonesScanned,
                    value1: blockedCount
                );
        }
    }

    /// <summary>
    /// Clears the entire maintained-view cache. Reserved for scene changes and
    /// other events that make every prior quest-resolution answer structurally
    /// invalid. Per-fact events must call <see cref="InvalidateAffected"/> instead.
    /// </summary>
    public void InvalidateAll(ChangeSet reason)
    {
        _cache.Clear();
        _blockingZoneCache.Clear();
        _dependencies?.Clear();
        _lastObservedVersion = _versionProvider();
        _ = reason;
    }

    private static string BuildCacheKey(string questKey, string currentScene) =>
        questKey + "\n" + (currentScene ?? string.Empty).ToUpperInvariant();
}
