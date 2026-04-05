using AdventureGuide.Graph;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
using AdventureGuide.State;

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
/// Priority algorithm (eight tiers; "direct" means <c>IsBlockedPath</c> is false):
/// <list type="number">
///   <item>Direct + same-zone, guaranteed loot — closest</item>
///   <item>Direct + same-zone, actionable — closest</item>
///   <item>Direct + same-zone, non-actionable — closest</item>
///   <item>Direct + cross-zone — fewest zone hops</item>
///   <item>Blocked-path + same-zone, guaranteed loot — closest</item>
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
    private readonly EntityGraph? _graph;
    private readonly LiveStateTracker? _liveState;
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

    public NavigationTargetSelector(QuestResolutionService resolution, ZoneRouter router,
        EntityGraph graph, LiveStateTracker liveState)
        : this(resolution.ResolveTargetsForNavigation, router, graph, liveState) { }

    /// <summary>Test seam: inject a custom resolver without a live resolution service.</summary>
    internal NavigationTargetSelector(
        Func<string, IReadOnlyList<ResolvedQuestTarget>> resolver,
        ZoneRouter router,
        EntityGraph? graph = null,
        LiveStateTracker? liveState = null)
    {
        _resolver  = resolver;
        _router    = router;
        _graph     = graph;
        _liveState = liveState;
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
            UpdateLivePositions(kv.Value, playerX, playerY, playerZ, currentZone);
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
    /// Priority (eight tiers; "direct" means <c>IsBlockedPath</c> is false):
    /// guaranteed-loot-direct → direct-actionable → direct-non-actionable →
    /// direct-cross-zone → guaranteed-loot-blocked → blocked-actionable →
    /// blocked-non-actionable → blocked-cross-zone.
    /// TravelToZone candidates are always skipped.
    /// </summary>

    /// <summary>
    /// Updates X/Y/Z and <see cref="ResolvedQuestTarget.IsActionable"/> on
    /// character targets each tick based on live scene state:
    /// <list type="bullet">
    /// <item>Alive NPC found: position updated to live coords, IsActionable forced
    /// to true (an alive NPC is always a valid kill target).</item>
    /// <item>Spawn completely empty (corpse rotted, no game object): position
    /// snapped to static graph spawn coordinates so the arrow points to the
    /// respawn spot, IsActionable set to false.</item>
    /// <item>Corpse present (game object exists, NPC dead): both fields left
    /// unchanged — CorpseContainsItem in the resolution pipeline already set
    /// them correctly.</item>
    /// </list>
    /// Static targets (mining nodes, item bags, chests, zone lines) have
    /// non-Character TargetNode types and are never modified. Cross-zone targets
    /// are skipped.
    /// </summary>
    private void UpdateLivePositions(
        IReadOnlyList<ResolvedQuestTarget> targets,
        float playerX, float playerY, float playerZ,
        string currentZone)
    {
        if (_liveState == null || _graph == null) return;

        for (int i = 0; i < targets.Count; i++)
        {
            var t = targets[i];

            // Only same-scene character targets need live updates.
            if (t.TargetNode.Node.Type != NodeType.Character)
                continue;
            if (t.Scene != null
                && !string.Equals(t.Scene, currentZone, StringComparison.OrdinalIgnoreCase))
                continue;
            if (t.SourceKey == null)
                continue;

            var spawnNode = _graph.GetNode(t.SourceKey);
            // SourceKey may resolve to a Character node in the rare no-spawn-edges
            // fallback path. GetLiveNpcForTracking expects a SpawnPoint node.
            if (spawnNode?.Type != NodeType.SpawnPoint)
                continue;

            var pos = _liveState.GetLiveNpcPosition(spawnNode);
            if (pos != null)
            {
                // NPC alive: update to live position and ensure actionable.
                // Corrects stale isActionable=false from when the previous
                // NPC's corpse had no required loot.
                t.X = pos.Value.x;
                t.Y = pos.Value.y;
                t.Z = pos.Value.z;
                t.IsActionable = true;
            }
            else if (_liveState.IsSpawnEmpty(spawnNode))
            {
                // Spawn completely empty (corpse rotted, no game object).
                // Point to static spawn coordinates so the arrow shows the
                // respawn location rather than the last-seen corpse position.
                if (spawnNode.X.HasValue && spawnNode.Y.HasValue && spawnNode.Z.HasValue)
                {
                    t.X = spawnNode.X.Value;
                    t.Y = spawnNode.Y.Value;
                    t.Z = spawnNode.Z.Value;
                }
                t.IsActionable = false;
            }
            // else: corpse is present (game object exists, NPC dead).
            // isActionable was set correctly by CorpseContainsItem during
            // resolution. Leave both position and actionability unchanged.
        }
    }

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

        return MakeSameZone(actionable.DirectGuaranteedLoot)    // tier 0: direct + same-zone, guaranteed loot
            ?? MakeSameZone(actionable.Direct)                  // tier 1: direct + same-zone, actionable
            ?? MakeSameZone(nonActionable.Direct)               // tier 2: direct + same-zone, non-actionable
            ?? MakeCrossZone(czDirect, czDirectHops)            // tier 3: direct + cross-zone
            ?? MakeSameZone(actionable.BlockedGuaranteedLoot)   // tier 4: blocked + same-zone, guaranteed loot
            ?? MakeSameZone(actionable.Blocked)                 // tier 5: blocked + same-zone, actionable
            ?? MakeSameZone(nonActionable.Blocked)              // tier 6: blocked + same-zone, non-actionable
            ?? MakeCrossZone(czBlocked, czBlockedHops);         // tier 7: blocked + cross-zone
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
        public ResolvedQuestTarget? DirectGuaranteedLoot;
        public float DirectGuaranteedLootDist;
        public ResolvedQuestTarget? BlockedGuaranteedLoot;
        public float BlockedGuaranteedLootDist;

        public static BestSameZone Init() => new BestSameZone
        {
            DirectDist = float.MaxValue,
            BlockedDist = float.MaxValue,
            DirectGuaranteedLootDist = float.MaxValue,
            BlockedGuaranteedLootDist = float.MaxValue,
        };

        public void Consider(ResolvedQuestTarget t, float dist)
        {
            if (t.IsGuaranteedLoot)
            {
                if (!t.IsBlockedPath)
                { if (dist < DirectGuaranteedLootDist) { DirectGuaranteedLoot = t; DirectGuaranteedLootDist = dist; } }
                else
                { if (dist < BlockedGuaranteedLootDist) { BlockedGuaranteedLoot = t; BlockedGuaranteedLootDist = dist; } }
                return; // Do not also populate the regular actionable slot.
            }
            if (!t.IsBlockedPath)
            { if (dist < DirectDist)  { Direct  = t; DirectDist  = dist; } }
            else
            { if (dist < BlockedDist) { Blocked = t; BlockedDist = dist; } }
        }
    }
}
