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
    private readonly Func<int> _versionProvider;
    private readonly Dictionary<string, QuestResolutionRecord> _cache = new(StringComparer.Ordinal);
    private int _lastBatchKeyCount;
    private IReadOnlyList<AdventureGuide.Diagnostics.QuestCostSample> _topQuestCosts = Array.Empty<AdventureGuide.Diagnostics.QuestCostSample>();

    public QuestResolutionService(
        CompiledGuideModel guide,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver,
        ZoneRouter? zoneRouter,
        QuestTargetProjector projector,
        GuideDependencyEngine? dependencies = null,
        Func<int>? versionProvider = null
    )
    {
        _guide = guide;
        _frontier = frontier;
        _projector = projector;
        _dependencies = dependencies;
        _versionProvider = versionProvider ?? (() => 0);
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
        var resolutionSession = session ?? new SourceResolver.ResolutionSession();
        var record = ResolveOrBuildRecord(questKey, currentScene, resolutionSession, tracer);
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
        var results = new Dictionary<string, QuestResolutionRecord>(StringComparer.Ordinal);
        var resolutionSession = session ?? new SourceResolver.ResolutionSession();
        var seenKeys = new HashSet<string>(StringComparer.Ordinal);
        var questCosts = new List<AdventureGuide.Diagnostics.QuestCostSample>();
        foreach (var questKey in questKeys)
        {
            if (string.IsNullOrWhiteSpace(questKey) || !seenKeys.Add(questKey))
                continue;

            long start = System.Diagnostics.Stopwatch.GetTimestamp();
            var record = ResolveOrBuildRecord(questKey, currentScene, resolutionSession, tracer);
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
        foreach (var derivedKey in affectedDerivedKeys)
        {
            if (derivedKey.Kind == GuideDerivedKind.QuestTargets)
                _cache.Remove(derivedKey.Key);
        }
    }

    private QuestResolutionRecord? ResolveOrBuildRecord(
        string questKey,
        string currentScene,
        SourceResolver.ResolutionSession session,
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

        QuestResolutionRecord record;
        if (_dependencies == null)
        {
            record = BuildRecord(questKey, currentScene, questIndex, session, tracer);
        }
        else
        {
            using (_dependencies.BeginCollection(new GuideDerivedKey(GuideDerivedKind.QuestTargets, cacheKey)))
                record = BuildRecord(questKey, currentScene, questIndex, session, tracer);
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
        var frontier = new List<FrontierEntry>();
        _frontier.Resolve(questIndex, frontier, -1, tracer);
        var compiledTargets = _questTargetResolver.Resolve(questIndex, currentScene, frontier, session, tracer);
        var navigationTargets = _projector.Project(compiledTargets, currentScene);
        return new QuestResolutionRecord(
            questKey,
            currentScene,
            questIndex,
            frontier,
            compiledTargets,
            navigationTargets
        );
    }

    /// <summary>
    /// Clears the entire maintained-view cache. Reserved for scene changes and
    /// other events that make every prior quest-resolution answer structurally
    /// invalid. Per-fact events must call <see cref="InvalidateAffected"/> instead.
    /// </summary>
    public void InvalidateAll(GuideChangeSet reason)
    {
        _cache.Clear();
        _dependencies?.Clear();
        _ = reason;
    }

    private static string BuildCacheKey(string questKey, string currentScene) =>
        questKey + "\n" + (currentScene ?? string.Empty).ToUpperInvariant();
}
