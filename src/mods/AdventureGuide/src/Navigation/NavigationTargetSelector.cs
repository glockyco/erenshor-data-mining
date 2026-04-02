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
/// Priority algorithm:
/// <list type="number">
///   <item>Same-zone, actionable, non-TravelToZone — closest by metric distance</item>
///   <item>Same-zone, non-actionable, non-TravelToZone — closest by metric distance</item>
///   <item>Cross-zone — fewest zone hops</item>
/// </list>
/// TravelToZone candidates are always skipped: they are zone-exit waypoints, not quest
/// objectives. NAV navigates to the zone exit via its own <c>EffectiveTarget</c>
/// computation when the winning target is cross-zone.
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
    /// Priority: same-zone actionable (closest) → same-zone non-actionable (closest)
    ///           → cross-zone (fewest hops, -1 if no route).
    /// TravelToZone candidates are always skipped.
    /// </summary>
    internal static SelectedNavTarget? SelectBest(
        IReadOnlyList<ResolvedQuestTarget> targets,
        float playerX, float playerY, float playerZ,
        string currentZone,
        ZoneRouter router)
    {
        ResolvedQuestTarget? bestActionable = null;
        float bestActionableDist = float.MaxValue;

        ResolvedQuestTarget? bestNonActionable = null;
        float bestNonActionableDist = float.MaxValue;

        // Cross-zone: first collect one representative target per destination zone
        // (O(targets) with O(1) dict lookups), then score each unique zone using the
        // hop-count cache (O(unique zones), no BFS per target).
        Dictionary<string, ResolvedQuestTarget>? crossZoneReps = null;
        ResolvedQuestTarget? bestCrossZone = null;
        int bestHops = int.MaxValue;

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
                if (t.IsActionable)
                {
                    if (d < bestActionableDist)
                    {
                        bestActionable = t;
                        bestActionableDist = d;
                    }
                }
                else
                {
                    if (d < bestNonActionableDist)
                    {
                        bestNonActionable = t;
                        bestNonActionableDist = d;
                    }
                }
            }
            else if (!string.IsNullOrEmpty(t.Scene))
            {
                // Record only the first target seen per destination zone.
                // Which specific target within that zone to navigate to is a
                // decision that belongs to a later in-zone resolution.
                crossZoneReps ??= new Dictionary<string, ResolvedQuestTarget>(
                    StringComparer.OrdinalIgnoreCase);
                if (!crossZoneReps.ContainsKey(t.Scene!))
                    crossZoneReps[t.Scene!] = t;
            }
        }

        // Score unique destination zones — O(unique zones) GetHopCount calls,
        // each O(1) after the first call populates the router's hop cache.
        if (crossZoneReps != null)
        {
            foreach (var kv in crossZoneReps)
            {
                int hops = router.GetHopCount(currentZone, kv.Key);
                if (hops < bestHops)
                {
                    bestHops      = hops;
                    bestCrossZone = kv.Value;
                }
            }

            // Fallback: all zones unreachable; return any candidate so callers
            // know cross-zone targets exist even if we can't route to them.
            if (bestCrossZone == null)
            {
                foreach (var kv in crossZoneReps)
                {
                    bestCrossZone = kv.Value;
                    break;
                }
            }
        }

        if (bestActionable != null)
            return new SelectedNavTarget
            {
                Target = bestActionable,
                IsSameZone = true,
            };

        if (bestNonActionable != null)
            return new SelectedNavTarget
            {
                Target = bestNonActionable,
                IsSameZone = true,
            };

        if (bestCrossZone != null)
            return new SelectedNavTarget
            {
                Target = bestCrossZone,
                IsSameZone = false,
                // int.MaxValue means only no-route candidates were seen → -1 sentinel.
                HopCount = bestHops == int.MaxValue ? -1 : bestHops,
            };

        return null;
    }
}
