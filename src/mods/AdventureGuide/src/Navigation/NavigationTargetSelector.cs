using AdventureGuide.Position;
using AdventureGuide.Resolution;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// One quest's pre-selected best navigation target, computed on a shared throttled timer.
/// Both <see cref="NavigationEngine"/> and <c>TrackerPanel</c> read from the same cache so
/// they can never disagree about which target is "closest" for a given quest.
/// </summary>
public struct SelectedNavTarget
{
    /// <summary>The winning resolved target.</summary>
    public ResolvedQuestTarget Target;

    /// <summary>True when <see cref="Target"/> is in the player's current zone.</summary>
    public bool IsSameZone;

    /// <summary>
    /// Metric distance to <see cref="Target"/>'s world position.
    /// Valid when <see cref="IsSameZone"/> is true.
    /// </summary>
    public float Distance;

    /// <summary>
    /// Number of zone transitions required to reach the target zone.
    /// Valid when <see cref="IsSameZone"/> is false. -1 means no route exists.
    /// </summary>
    public int HopCount;
}

/// <summary>
/// Throttled per-key best-target selection shared by <see cref="NavigationEngine"/> and
/// <c>TrackerPanel</c>.
///
/// Computes the canonical "best target" for each requested node key once per
/// <see cref="UpdateInterval"/> (or immediately when forced) using a priority-ordered
/// algorithm:
/// <list type="number">
///   <item>Same-zone, actionable, non-TravelToZone — closest by metric distance</item>
///   <item>Same-zone, non-actionable, non-TravelToZone — closest by metric distance</item>
///   <item>Cross-zone — fewest zone hops</item>
/// </list>
/// TravelToZone candidates are always skipped: they are zone-exit waypoints, not quest
/// objectives. NAV navigates to the zone exit via its own <c>EffectiveTarget</c>
/// computation when the winning target is cross-zone.
///
/// Plugin calls <see cref="Tick"/> once per frame (before NavigationEngine.Update), passing
/// the union of nav-set keys and tracker quest keys. Both consumers then call
/// <see cref="TryGet"/> and format display text independently.
/// </summary>
public sealed class NavigationTargetSelector
{
    private const float UpdateInterval = 0.5f;

    private readonly QuestResolutionService _resolution;
    private readonly ZoneRouter _router;
    private readonly Dictionary<string, SelectedNavTarget> _cache =
        new(StringComparer.Ordinal);

    // Start at the interval so the very first Tick fires immediately.
    private float _timer = UpdateInterval;

    /// <summary>
    /// Monotonically increasing version. Incremented after each cache refresh so
    /// <see cref="NavigationEngine"/> can detect when new data is available.
    /// </summary>
    public int Version { get; private set; }

    public NavigationTargetSelector(QuestResolutionService resolution, ZoneRouter router)
    {
        _resolution = resolution;
        _router = router;
    }

    /// <summary>
    /// Called once per frame by Plugin before consumers read. Refreshes the cache when the
    /// throttle interval expires or <paramref name="force"/> is true.
    ///
    /// Passing a lazy iterator for <paramref name="nodeKeys"/> avoids allocation on
    /// suppressed frames because the iterator is only consumed when a refresh runs.
    /// Duplicate keys in the iterator are deduplicated via the dictionary.
    /// </summary>
    public void Tick(Vector3 playerPos, string currentZone,
                     IEnumerable<string> nodeKeys, bool force = false)
    {
        _timer += Time.deltaTime;
        if (!force && _timer < UpdateInterval)
            return;

        _timer = 0f;
        _cache.Clear();

        foreach (var key in nodeKeys)
        {
            if (_cache.ContainsKey(key))
                continue;

            var targets = _resolution.ResolveTargetsForNavigation(key);
            if (targets.Count == 0)
                continue;

            var selected = SelectBest(targets, playerPos.x, playerPos.y, playerPos.z, currentZone, _router);
            if (selected.HasValue)
                _cache[key] = selected.Value;
        }

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

        // Cross-zone tracking: fewest hops wins; no-route targets are kept as fallback
        // only when no routable cross-zone target exists.
        ResolvedQuestTarget? bestCrossZone = null;
        int bestHops = int.MaxValue; // int.MaxValue means "only no-route candidates seen"

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
            else
            {
                if (string.IsNullOrEmpty(t.Scene))
                    continue;

                var route = router.FindRoute(currentZone, t.Scene!);
                if (route != null)
                {
                    int hops = Math.Max(0, route.Path.Count - 1);
                    if (hops < bestHops)
                    {
                        bestHops = hops;
                        bestCrossZone = t;
                    }
                }
                else if (bestCrossZone == null)
                {
                    // No route exists; keep as a last-resort candidate so callers know
                    // the target exists even if we can't route to it.
                    bestCrossZone = t;
                }
            }
        }

        if (bestActionable != null)
            return new SelectedNavTarget
            {
                Target = bestActionable,
                IsSameZone = true,
                Distance = bestActionableDist,
            };

        if (bestNonActionable != null)
            return new SelectedNavTarget
            {
                Target = bestNonActionable,
                IsSameZone = true,
                Distance = bestNonActionableDist,
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
