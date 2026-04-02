using AdventureGuide.Position;
using AdventureGuide.Resolution;

namespace AdventureGuide.Navigation;

/// <summary>
/// One quest's pre-selected best navigation target.
/// Both <see cref="NavigationEngine"/> and <c>TrackerPanel</c> read from the same cache.
/// Consumers compute distance inline from <c>Target.X/Y/Z</c>.
/// </summary>
public struct SelectedNavTarget
{
    /// <summary>The winning resolved target.</summary>
    public ResolvedQuestTarget Target;

    /// <summary>True when <see cref="Target"/> is in the player's current zone.</summary>
    public bool IsSameZone;

    /// <summary>
    /// Number of zone transitions required to reach the target zone.
    /// Valid when <see cref="IsSameZone"/> is false. -1 means no route exists.
    /// </summary>
    public int HopCount;

    /// <summary>True when <see cref="Target"/> belongs to a blocked-but-feasible route.</summary>
    public bool IsBlockedPath;
}

/// <summary>
/// Per-key best-target selection shared by <see cref="NavigationEngine"/> and
/// <c>TrackerPanel</c>.
///
/// <see cref="Tick"/> re-evaluates the best target for every cached key on each
/// call. Callers that need a fresh target-list fetch (e.g. after a resolution or
/// scene change) pass <c>force=true</c>. Consumers compute distance inline from
/// <c>SelectedNavTarget.Target.X/Y/Z</c> — the struct does not carry a distance snapshot.
///
/// Priority algorithm (six tiers; "direct" means <c>IsBlockedPath</c> is false):
/// <list type="number">
///   <item>Direct + same-zone, actionable — closest</item>
///   <item>Direct + same-zone, non-actionable — closest</item>
///   <item>Direct + cross-zone — fewest zone hops</item>
///   <item>Blocked-path + same-zone, actionable — closest</item>
///   <item>Blocked-path + same-zone, non-actionable — closest</item>
///   <item>Blocked-path + cross-zone — fewest zone hops</item>
/// </list>
/// TravelToZone candidates are always skipped.
/// </summary>
public sealed class NavigationTargetSelector
{
    private readonly Func<string, IReadOnlyList<ResolvedQuestTarget>> _resolver;
    private readonly ZoneRouter _router;
    private readonly Dictionary<string, SelectedNavTarget> _cache =
        new(StringComparer.Ordinal);
    // Resolved target lists per key. Populated once per force tick; re-used
    // on every subsequent tick so ResolveTargetsForNavigation is not called
    // per frame. Cleared and rebuilt when the resolution plan or nav set changes.
    private readonly Dictionary<string, IReadOnlyList<ResolvedQuestTarget>> _targetLists =
        new(StringComparer.Ordinal);

    /// <summary>
    /// Monotonically increasing version. Incremented after each cache refresh so
    /// <see cref="NavigationEngine"/> can detect when new data is available.
    /// </summary>
    public int Version { get; private set; }

    public NavigationTargetSelector(QuestResolutionService resolution, ZoneRouter router)
        : this(resolution.ResolveTargetsForNavigation, router) { }

    /// <summary>Test seam: inject a custom resolver without a live resolution service.</summary>
    internal NavigationTargetSelector(
        Func<string, IReadOnlyList<ResolvedQuestTarget>> resolver, ZoneRouter router)
    {
        _resolver = resolver;
        _router   = router;
    }

    /// <summary>
    /// Called once per frame by Plugin before consumers read.
    ///
    /// <b>Every tick</b>: re-runs <see cref="SelectBest"/> for all cached keys using
    /// the current player position. <see cref="Version"/> is incremented when the
    /// selected target identity changes for any key, or when <paramref name="force"/> is
    /// true.
    ///
    /// <b>Forced tick</b> (<paramref name="force"/> is true): clears and rebuilds the
    /// target-list cache from <paramref name="nodeKeys"/>. Force is required when the
    /// resolution plan or nav key set has changed.
    ///
    /// <paramref name="nodeKeys"/> is consumed only on forced ticks, so passing a lazy
    /// iterator avoids allocation on non-forced frames.
    /// </summary>
    public void Tick(float playerX, float playerY, float playerZ, string currentZone,
                     IEnumerable<string> nodeKeys, bool force = false)
    {
        if (force)
        {
            _targetLists.Clear();
            _cache.Clear();

            foreach (var key in nodeKeys)
            {
                if (_targetLists.ContainsKey(key))
                    continue;
                var targets = _resolver(key);
                if (targets.Count > 0)
                    _targetLists[key] = targets;
            }
        }

        // Re-run SelectBest every tick using current player position.
        // With hop-count caching, SelectBest is O(targets) distance math +
        // O(unique_zones) O(1) lookups — cheap enough for per-frame execution.
        bool changed = false;
        foreach (var kv in _targetLists)
        {
            var selected = SelectBest(
                kv.Value, playerX, playerY, playerZ, currentZone, _router);
            if (selected.HasValue)
            {
                if (!_cache.TryGetValue(kv.Key, out var existing) ||
                    existing.Target.TargetNodeKey != selected.Value.Target.TargetNodeKey)
                {
                    _cache[kv.Key] = selected.Value;
                    changed = true;
                }
            }
            else if (_cache.Remove(kv.Key))
            {
                changed = true;
            }
        }

        if (force || changed)
            Version++;
    }

    /// <summary>
    /// Returns the pre-computed best target for <paramref name="nodeKey"/>.
    /// Returns false if the key was not in the last Tick's key set or had no targets.
    /// </summary>
    public bool TryGet(string nodeKey, out SelectedNavTarget target) =>
        _cache.TryGetValue(nodeKey, out target);

    /// <summary>
    /// Canonical best-target selection algorithm. Exposed as internal static for direct
    /// unit testing without requiring a live <see cref="QuestResolutionService"/>.
    ///
    /// Priority (six tiers; "direct" means <c>IsBlockedPath</c> is false):
    /// direct-actionable → direct-non-actionable → direct-cross-zone →
    /// blocked-actionable → blocked-non-actionable → blocked-cross-zone.
    /// TravelToZone candidates are always skipped.
    /// </summary>
    internal static SelectedNavTarget? SelectBest(
        IReadOnlyList<ResolvedQuestTarget> targets,
        float playerX, float playerY, float playerZ,
        string currentZone,
        ZoneRouter router)
    {
        var actionable    = BestSameZone.Init();
        var nonActionable = BestSameZone.Init();

        // Cross-zone: one representative per destination zone, split by
        // blocking status. Zone deduplication keeps the hop-count pass
        // O(unique zones) rather than O(targets).
        Dictionary<string, ResolvedQuestTarget>? crossZoneDirect  = null;
        Dictionary<string, ResolvedQuestTarget>? crossZoneBlocked = null;

        for (int i = 0; i < targets.Count; i++)
        {
            var t = targets[i];

            // Zone-exit waypoints are navigation artefacts, not objectives.
            if (t.Semantic.GoalKind == NavigationGoalKind.TravelToZone)
                continue;

            bool sameZone = t.Scene == null ||
                string.Equals(t.Scene, currentZone, StringComparison.OrdinalIgnoreCase);

            if (sameZone)
            {
                float dx = playerX - t.X, dy = playerY - t.Y, dz = playerZ - t.Z;
                float d = MathF.Sqrt(dx * dx + dy * dy + dz * dz);
                if (t.IsActionable) actionable.Consider(t, d);
                else                nonActionable.Consider(t, d);
            }
            else if (!string.IsNullOrEmpty(t.Scene))
            {
                // Record one candidate per destination zone within each
                // blocking half; which specific in-zone target to use is
                // decided during later in-zone resolution.
                if (!t.IsBlockedPath)
                {
                    crossZoneDirect ??= new Dictionary<string, ResolvedQuestTarget>(
                        StringComparer.OrdinalIgnoreCase);
                    if (!crossZoneDirect.ContainsKey(t.Scene!))
                        crossZoneDirect[t.Scene!] = t;
                }
                else
                {
                    crossZoneBlocked ??= new Dictionary<string, ResolvedQuestTarget>(
                        StringComparer.OrdinalIgnoreCase);
                    if (!crossZoneBlocked.ContainsKey(t.Scene!))
                        crossZoneBlocked[t.Scene!] = t;
                }
            }
        }

        // Score unique destination zones — O(unique zones) GetHopCount calls,
        // each O(1) after the first call populates the router's hop cache.
        var (czDirect,  czDirectHops)  = BestCrossZoneCandidate(crossZoneDirect,  currentZone, router);
        var (czBlocked, czBlockedHops) = BestCrossZoneCandidate(crossZoneBlocked, currentZone, router);

        return MakeSameZone(actionable.Direct)
            ?? MakeSameZone(nonActionable.Direct)
            ?? MakeCrossZone(czDirect, czDirectHops)
            ?? MakeSameZone(actionable.Blocked)
            ?? MakeSameZone(nonActionable.Blocked)
            ?? MakeCrossZone(czBlocked, czBlockedHops);
    }

    /// <summary>
    /// Returns the cross-zone representative with the fewest hops and that
    /// hop count. Returns <c>(null, -1)</c> when <paramref name="reps"/> is
    /// null. Hop count is -1 when all destination zones are unreachable.
    /// </summary>
    private static (ResolvedQuestTarget? Target, int Hops) BestCrossZoneCandidate(
        Dictionary<string, ResolvedQuestTarget>? reps,
        string currentZone,
        ZoneRouter router)
    {
        if (reps == null)
            return (null, -1);

        ResolvedQuestTarget? best = null;
        int bestHops = int.MaxValue;
        foreach (var kv in reps)
        {
            int hops = router.GetHopCount(currentZone, kv.Key);
            if (hops < bestHops) { bestHops = hops; best = kv.Value; }
        }

        // Fallback: all destination zones are unreachable; return any
        // candidate so callers know cross-zone targets exist.
        if (best == null)
            foreach (var kv in reps) { best = kv.Value; break; }

        return (best, bestHops == int.MaxValue ? -1 : bestHops);
    }

    private static SelectedNavTarget? MakeSameZone(ResolvedQuestTarget? t) =>
        t == null ? null : new SelectedNavTarget
        {
            Target        = t,
            IsSameZone    = true,
            IsBlockedPath = t.IsBlockedPath,
        };

    private static SelectedNavTarget? MakeCrossZone(ResolvedQuestTarget? t, int hops) =>
        t == null ? null : new SelectedNavTarget
        {
            Target        = t,
            IsSameZone    = false,
            HopCount      = hops,
            IsBlockedPath = t.IsBlockedPath,
        };

    /// <summary>
    /// Tracks the nearest direct (unblocked-path) and nearest blocked-path
    /// candidate within a single same-zone actionability tier.
    /// </summary>
    private struct BestSameZone
    {
        public ResolvedQuestTarget? Direct;
        public float DirectDist;
        public ResolvedQuestTarget? Blocked;
        public float BlockedDist;

        public static BestSameZone Init() =>
            new BestSameZone { DirectDist = float.MaxValue, BlockedDist = float.MaxValue };

        public void Consider(ResolvedQuestTarget t, float dist)
        {
            if (!t.IsBlockedPath)
            { if (dist < DirectDist)  { Direct  = t; DirectDist  = dist; } }
            else
            { if (dist < BlockedDist) { Blocked = t; BlockedDist = dist; } }
        }
    }
}
