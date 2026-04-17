using System.Diagnostics;
using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

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
    private const float DefaultRerankIntervalSeconds = 1f;

    private readonly Func<string, string, IReadOnlyList<ResolvedQuestTarget>> _resolver;
    private readonly ZoneRouter _router;
    private readonly CompiledGuideModel? _guide;
    private readonly LiveStateTracker? _liveState;
    private readonly PositionResolverRegistry? _positionResolvers;
    private readonly DiagnosticsCore? _diagnostics;
    private readonly Dictionary<string, SelectedNavTarget> _cache = new(StringComparer.Ordinal);

    // Per-key pre-decomposed target structure. Entries are retained across forced
    // ticks so their inner lists can be cleared and refilled without reallocation.
    private readonly Dictionary<string, TargetEntry> _entries = new(StringComparer.Ordinal);

    // Scratch collections for key-set management during forced ticks.
    private readonly HashSet<string> _activeKeys = new(StringComparer.Ordinal);
    private readonly List<string> _keysToEvict = new();
    private readonly Func<float> _clock;
    private readonly float _rerankInterval;
    private float _lastRerankTime = float.NegativeInfinity;
    private DiagnosticTrigger _lastForceReason = DiagnosticTrigger.Unknown;
    private int _lastResolvedTargetCount;

    /// <summary>
    /// Monotonically increasing version. Incremented after each cache refresh so
    /// <see cref="NavigationEngine"/> can detect when new data is available.
    /// </summary>
    public int Version { get; private set; }

    internal NavigationTargetSelector(
        NavigationTargetResolver resolution,
        ZoneRouter router,
        CompiledGuideModel guide,
        LiveStateTracker liveState,
        PositionResolverRegistry positionResolvers,
        DiagnosticsCore? diagnostics = null
    )
        : this(
            (key, scene) => resolution.Resolve(key, scene),
            router,
            guide,
            liveState,
            positionResolvers,
            diagnostics,
            () => UnityEngine.Time.time,
            DefaultRerankIntervalSeconds
        ) { }

    internal NavigationTargetSelector(
        Func<string, string, IReadOnlyList<ResolvedQuestTarget>> resolver,
        ZoneRouter router,
        CompiledGuideModel? guide = null,
        LiveStateTracker? liveState = null,
        PositionResolverRegistry? positionResolvers = null,
        DiagnosticsCore? diagnostics = null,
        Func<float>? clock = null,
        float rerankInterval = 0f
    )
    {
        _resolver = resolver;
        _router = router;
        _guide = guide;
        _liveState = liveState;
        _positionResolvers = positionResolvers;
        _diagnostics = diagnostics;
        _clock = clock ?? (() => 0f);
        _rerankInterval = rerankInterval;
    }

    /// <summary>
    /// Called once per frame by Plugin before consumers read.
    ///
    /// <b>Every tick</b>: re-runs <see cref="SelectBestCore"/> for all cached keys
    /// using the current player position. <see cref="Version"/> is incremented when
    /// the selected target identity changes for any key, or when <paramref name="force"/>
    /// is true.
    ///
    /// <b>Forced tick</b> (<paramref name="force"/> is true): resolves fresh target lists
    /// from <paramref name="nodeKeys"/> and decomposes each into same-zone and cross-zone
    /// partitions stored in the per-key <see cref="TargetEntry"/>. Cross-zone reps are
    /// pre-built here so <see cref="SelectBestCore"/> never allocates on regular ticks.
    ///
    /// <paramref name="nodeKeys"/> is only consumed on forced ticks, so passing a lazy
    /// iterator avoids allocation on non-forced frames.
    /// </summary>
    internal void Tick(
        float playerX,
        float playerY,
        float playerZ,
        string currentZone,
        IEnumerable<string> nodeKeys,
        bool force = false,
        DiagnosticTrigger forceReason = DiagnosticTrigger.Unknown
    )
    {
        var context = DiagnosticsContext.Root(force ? forceReason : DiagnosticTrigger.Unknown);
        var token = _diagnostics?.BeginSpan(
            DiagnosticSpanKind.NavSelectorTick,
            context,
            primaryKey: currentZone
        );
        long startTick = Stopwatch.GetTimestamp();
        try
        {
            float now = _clock();
            bool due = now - _lastRerankTime >= _rerankInterval;
            if (!force && !due)
                return;
            _lastRerankTime = now;

            if (force)
            {
                _lastForceReason = forceReason;
                _lastResolvedTargetCount = 0;
                _diagnostics?.RecordEvent(
                    new DiagnosticEvent(
                        DiagnosticEventKind.SelectorRefreshForced,
                        context,
                        timestampTicks: startTick,
                        primaryKey: currentZone,
                        value0: _entries.Count,
                        value1: 0
                    )
                );

                _activeKeys.Clear();
                foreach (var key in nodeKeys)
                {
                    _activeKeys.Add(key);
                    var targets = _resolver(key, currentZone);
                    _lastResolvedTargetCount += targets.Count;
                    if (targets.Count == 0)
                        continue;
                    if (!_entries.TryGetValue(key, out var entry))
                    {
                        entry = new TargetEntry();
                        _entries[key] = entry;
                    }
                    entry.Rebuild(targets, currentZone);
                }

                _keysToEvict.Clear();
                foreach (var k in _entries.Keys)
                    if (!_activeKeys.Contains(k))
                        _keysToEvict.Add(k);
                foreach (var k in _keysToEvict)
                    _entries.Remove(k);
                _cache.Clear();
            }

            bool changed = false;
            foreach (var kv in _entries)
            {
                UpdateLivePositions(kv.Value, currentZone);
                var selected = SelectBestCore(
                    kv.Value,
                    playerX,
                    playerY,
                    playerZ,
                    currentZone,
                    _router
                );
                if (selected.HasValue)
                {
                    bool targetChanged =
                        !_cache.TryGetValue(kv.Key, out var existing)
                        || !string.Equals(
                            existing.Target.TargetInstanceKey,
                            selected.Value.Target.TargetInstanceKey,
                            StringComparison.Ordinal
                        );
                    _cache[kv.Key] = selected.Value;
                    if (targetChanged)
                        changed = true;
                }
                else if (_cache.Remove(kv.Key))
                {
                    changed = true;
                }
            }

            if (force || changed)
                Version++;
        }
        finally
        {
            if (token != null)
                _diagnostics!.EndSpan(
                    token.Value,
                    Stopwatch.GetTimestamp() - startTick,
                    value0: _entries.Count,
                    value1: _lastResolvedTargetCount
                );
        }
    }

    /// <summary>
    /// Returns the pre-computed best target for <paramref name="nodeKey"/>.
    /// Returns false if the key was not in the last Tick's key set or had no targets.
    /// </summary>
    public bool TryGet(string nodeKey, out SelectedNavTarget target) =>
        _cache.TryGetValue(nodeKey, out target);

    internal string DumpCandidates(
        float playerX,
        float playerY,
        float playerZ,
        string currentZone,
        string? selectedTargetNodeKey = null
    )
    {
        var sb = new System.Text.StringBuilder();
        foreach (var kv in _entries)
        {
            if (!_cache.TryGetValue(kv.Key, out var selected))
                continue;
            if (
                selectedTargetNodeKey != null
                && !string.Equals(
                    selected.Target.TargetNodeKey,
                    selectedTargetNodeKey,
                    StringComparison.Ordinal
                )
            )
                continue;

            sb.AppendLine($"RequestKey: {kv.Key}");
            sb.AppendLine(
                $"  Selected: {selected.Target.TargetNodeKey} source={selected.Target.SourceKey} actionable={selected.Target.IsActionable} guaranteed={selected.Target.IsGuaranteedLoot} blocked={selected.Target.IsBlockedPath}"
            );

            for (int i = 0; i < kv.Value.SameZone.Count; i++)
            {
                var target = kv.Value.SameZone[i];
                float dx = playerX - target.X;
                float dy = playerY - target.Y;
                float dz = playerZ - target.Z;
                float dist = MathF.Sqrt(dx * dx + dy * dy + dz * dz);
                sb.AppendLine(
                    $"  Candidate[{i}]: key={target.TargetNodeKey} source={target.SourceKey} scene={target.Scene ?? "(none)"} dist={dist:F1} actionable={target.IsActionable} guaranteed={target.IsGuaranteedLoot} blocked={target.IsBlockedPath}"
                );
            }
        }

        if (sb.Length == 0)
        {
            return selectedTargetNodeKey == null
                ? "No cached navigation candidates"
                : $"No cached navigation candidates for selected target '{selectedTargetNodeKey}'";
        }

        return sb.ToString();
    }

    internal NavigationDiagnosticsSnapshot ExportDiagnosticsSnapshot()

    {
        return new NavigationDiagnosticsSnapshot(
            lastForceReason: _lastForceReason,
            cacheEntryCount: _entries.Count,
            currentTargetKey: null,
            lastResolvedTargetCount: _lastResolvedTargetCount
        );
    }

    /// <summary>
    /// Refreshes cached same-zone mutable targets from canonical live truth.
    ///
    /// Character targets follow live spawn occupancy. Mining and item-bag targets
    /// refresh through the shared position-resolver registry so selector cache
    /// truth matches fresh resolution without requiring a forced rebuild.
    /// </summary>
    private void UpdateLivePositions(TargetEntry entry, string currentZone)
    {
        for (int i = 0; i < entry.SameZoneMutableTargets.Count; i++)
        {
            var t = entry.SameZoneMutableTargets[i];
            switch (t.TargetNode.Node.Type)
            {
                case NodeType.Character:
                    RefreshCharacterTarget(t);
                    break;
                case NodeType.MiningNode:
                case NodeType.ItemBag:
                    RefreshResolvedPositionTarget(t);
                    break;
            }
        }
    }

    private void RefreshCharacterTarget(ResolvedQuestTarget target)
    {
        if (_liveState == null || _guide == null || target.SourceKey == null)
            return;

        var spawnNode = _guide.GetNode(target.SourceKey);
        // SourceKey may resolve to a Character node in the rare no-spawn-edges
        // fallback path. GetLiveNpcPosition expects a SpawnPoint node.
        if (spawnNode?.Type != NodeType.SpawnPoint)
            return;

        var pos = _liveState.GetLiveNpcPosition(spawnNode);
        if (pos != null)
        {
            // NPC alive: update to live position and ensure actionable.
            // Corrects stale isActionable=false from when the previous
            // NPC's corpse had no required loot.
            target.X = pos.Value.x;
            target.Y = pos.Value.y;
            target.Z = pos.Value.z;
            target.IsActionable = true;
        }
        else if (_liveState.IsSpawnEmpty(spawnNode))
        {
            // Spawn completely empty (corpse rotted, no game object).
            // Point to static spawn coordinates so the arrow shows the
            // respawn location rather than the last-seen corpse position.
            if (spawnNode.X.HasValue && spawnNode.Y.HasValue && spawnNode.Z.HasValue)
            {
                target.X = spawnNode.X.Value;
                target.Y = spawnNode.Y.Value;
                target.Z = spawnNode.Z.Value;
            }
            target.IsActionable = false;
        }
        // else: corpse is present (game object exists, NPC dead).
        // isActionable was set correctly by CorpseContainsItem during
        // resolution. Leave both position and actionability unchanged.
    }

    private void RefreshResolvedPositionTarget(ResolvedQuestTarget target)
    {
        if (_positionResolvers == null)
            return;

        string nodeKey = target.SourceKey ?? target.TargetNodeKey;
        var positions = new List<ResolvedPosition>();
        _positionResolvers.Resolve(nodeKey, positions);
        if (positions.Count == 0)
            return;

        ResolvedPosition position = positions[0];
        target.X = position.X;
        target.Y = position.Y;
        target.Z = position.Z;
        target.IsActionable = position.IsActionable;

    }

    /// <summary>
    /// Canonical best-target selection algorithm. Exposed as internal static for direct
    /// unit testing without requiring a live runtime resolver.
    ///
    /// Builds a temporary <see cref="TargetEntry"/> and delegates to
    /// <see cref="SelectBestCore"/>. Allocates; not called from the per-frame hot path.
    ///
    /// Priority (eight tiers; "direct" means <c>IsBlockedPath</c> is false):
    /// guaranteed-loot-direct → direct-actionable → direct-non-actionable →
    /// direct-cross-zone → guaranteed-loot-blocked → blocked-actionable →
    /// blocked-non-actionable → blocked-cross-zone.
    /// TravelToZone candidates are always skipped.
    /// </summary>
    internal static SelectedNavTarget? SelectBest(
        IReadOnlyList<ResolvedQuestTarget> targets,
        float playerX,
        float playerY,
        float playerZ,
        string currentZone,
        ZoneRouter router
    )
    {
        // Build a temporary TargetEntry. Allocates; SelectBest is only called from
        // tests and manual profiling, never from the per-frame hot path.
        var entry = new TargetEntry();
        entry.Rebuild(targets, currentZone);
        return SelectBestCore(entry, playerX, playerY, playerZ, currentZone, router);
    }

    /// <summary>
    /// Hot-path best-target selection over pre-decomposed <see cref="TargetEntry"/> data.
    ///
    /// Cost: O(<see cref="TargetEntry.SameZone"/>) distance math +
    /// O(unique cross-zone destination zones) hop lookups.
    /// No heap allocation because cross-zone representatives were pre-built at force time.
    /// </summary>
    private static SelectedNavTarget? SelectBestCore(
        TargetEntry entry,
        float playerX,
        float playerY,
        float playerZ,
        string currentZone,
        ZoneRouter router
    )
    {
        var actionable = BestSameZone.Init();
        var nonActionable = BestSameZone.Init();

        // Score same-zone targets only — cross-zone reps are pre-computed in entry.
        for (int i = 0; i < entry.SameZone.Count; i++)
        {
            var t = entry.SameZone[i];
            float dx = playerX - t.X,
                dy = playerY - t.Y,
                dz = playerZ - t.Z;
            float d = MathF.Sqrt(dx * dx + dy * dy + dz * dz);
            if (t.IsActionable)
                actionable.Consider(t, d);
            else
                nonActionable.Consider(t, d);
        }

        // Cross-zone: use pre-built reps, no allocation.
        var czDirect = entry.CrossZoneDirect.Count > 0 ? entry.CrossZoneDirect : null;
        var czBlocked = entry.CrossZoneBlocked.Count > 0 ? entry.CrossZoneBlocked : null;
        var (czDirectTarget, czDirectHops) = BestCrossZoneCandidate(czDirect, currentZone, router);
        var (czBlockedTarget, czBlockedHops) = BestCrossZoneCandidate(
            czBlocked,
            currentZone,
            router
        );

        return MakeSameZone(actionable.DirectGuaranteedLoot) // tier 0: direct + same-zone, guaranteed loot
            ?? MakeSameZone(actionable.Direct) // tier 1: direct + same-zone, actionable
            ?? MakeSameZone(nonActionable.Direct) // tier 2: direct + same-zone, non-actionable
            ?? MakeCrossZone(czDirectTarget, czDirectHops) // tier 3: direct + cross-zone
            ?? MakeSameZone(actionable.BlockedGuaranteedLoot) // tier 4: blocked + same-zone, guaranteed loot
            ?? MakeSameZone(actionable.Blocked) // tier 5: blocked + same-zone, actionable
            ?? MakeSameZone(nonActionable.Blocked) // tier 6: blocked + same-zone, non-actionable
            ?? MakeCrossZone(czBlockedTarget, czBlockedHops); // tier 7: blocked + cross-zone
    }

    /// <summary>
    /// Returns the cross-zone representative with the fewest hops and that
    /// hop count. Returns <c>(null, -1)</c> when <paramref name="reps"/> is
    /// null. Hop count is -1 when all destination zones are unreachable.
    /// </summary>
    private static (ResolvedQuestTarget? Target, int Hops) BestCrossZoneCandidate(
        Dictionary<string, ResolvedQuestTarget>? reps,
        string currentZone,
        ZoneRouter router
    )
    {
        if (reps == null)
            return (null, -1);

        ResolvedQuestTarget? best = null;
        int bestHops = int.MaxValue;
        foreach (var kv in reps)
        {
            int hops = router.GetHopCount(currentZone, kv.Key);
            if (hops < bestHops)
            {
                bestHops = hops;
                best = kv.Value;
            }
        }

        // Fallback: all destination zones are unreachable; return any
        // candidate so callers know cross-zone targets exist.
        if (best == null)
            foreach (var kv in reps)
            {
                best = kv.Value;
                break;
            }

        return (best, bestHops == int.MaxValue ? -1 : bestHops);
    }

    private static SelectedNavTarget? MakeSameZone(ResolvedQuestTarget? t) =>
        t == null
            ? null
            : new SelectedNavTarget
            {
                Target = t,
                IsSameZone = true,
                IsBlockedPath = t.IsBlockedPath,
            };

    private static SelectedNavTarget? MakeCrossZone(ResolvedQuestTarget? t, int hops) =>
        t == null
            ? null
            : new SelectedNavTarget
            {
                Target = t,
                IsSameZone = false,
                HopCount = hops,
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

        public static BestSameZone Init() =>
            new BestSameZone
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
                {
                    if (dist < DirectGuaranteedLootDist)
                    {
                        DirectGuaranteedLoot = t;
                        DirectGuaranteedLootDist = dist;
                    }
                }
                else
                {
                    if (dist < BlockedGuaranteedLootDist)
                    {
                        BlockedGuaranteedLoot = t;
                        BlockedGuaranteedLootDist = dist;
                    }
                }
                return; // Do not also populate the regular actionable slot.
            }
            if (!t.IsBlockedPath)
            {
                if (dist < DirectDist)
                {
                    Direct = t;
                    DirectDist = dist;
                }
            }
            else
            {
                if (dist < BlockedDist)
                {
                    Blocked = t;
                    BlockedDist = dist;
                }
            }
        }
    }

    /// <summary>
    /// Per-key pre-decomposed target structure owned by <see cref="NavigationTargetSelector"/>.
    ///
    /// Rebuilt on each forced <see cref="Tick"/>; inner collections are retained across
    /// force ticks so they can be cleared and refilled without reallocation on every
    /// live-world event. The same <see cref="ResolvedQuestTarget"/> objects appear in
    /// <see cref="All"/>, <see cref="SameZone"/>, and <see cref="SameZoneMutableTargets"/> —
    /// mutations by <see cref="UpdateLivePositions"/> propagate consistently.
    /// </summary>
    private sealed class TargetEntry
    {
        /// <summary>Full target list; objects are shared with the sub-lists.</summary>
        public IReadOnlyList<ResolvedQuestTarget> All = Array.Empty<ResolvedQuestTarget>();

        /// <summary>
        /// Same-zone targets (Scene == null or Scene == currentZone at force time),
        /// excluding TravelToZone artefacts. Iterated by <see cref="SelectBestCore"/>.
        /// </summary>
        public readonly List<ResolvedQuestTarget> SameZone = new();

        /// <summary>
        /// Same-zone targets whose position or actionability can change while the
        /// selector cache remains valid.
        /// </summary>
        public readonly List<ResolvedQuestTarget> SameZoneMutableTargets = new();

        /// <summary>
        /// Cross-zone representatives for unblocked-path targets: one per destination
        /// zone name. Reused dict avoids per-tick allocation.
        /// </summary>
        public readonly Dictionary<string, ResolvedQuestTarget> CrossZoneDirect = new(
            StringComparer.OrdinalIgnoreCase
        );

        /// <summary>
        /// Cross-zone representatives for blocked-path targets: one per destination
        /// zone name. Reused dict avoids per-tick allocation.
        /// </summary>
        public readonly Dictionary<string, ResolvedQuestTarget> CrossZoneBlocked = new(
            StringComparer.OrdinalIgnoreCase
        );

        /// <summary>
        /// Decompose <paramref name="all"/> into same-zone and cross-zone partitions
        /// for <paramref name="currentZone"/>. Called once per forced tick.
        /// </summary>
        public void Rebuild(IReadOnlyList<ResolvedQuestTarget> all, string currentZone)
        {
            All = all;
            SameZone.Clear();
            SameZoneMutableTargets.Clear();
            CrossZoneDirect.Clear();
            CrossZoneBlocked.Clear();

            for (int i = 0; i < all.Count; i++)
            {
                var t = all[i];
                // TravelToZone markers are navigation artefacts, not objectives.
                if (t.Semantic.GoalKind == NavigationGoalKind.TravelToZone)
                    continue;

                bool sameZone =
                    t.Scene == null
                    || string.Equals(t.Scene, currentZone, StringComparison.OrdinalIgnoreCase);
                if (sameZone)
                {
                    SameZone.Add(t);
                    if (
                        t.TargetNode.Node.Type
                        is NodeType.Character or NodeType.MiningNode or NodeType.ItemBag
                    )
                        SameZoneMutableTargets.Add(t);
                }
                else if (!string.IsNullOrEmpty(t.Scene))
                {
                    // One representative per destination zone, split by blocking.
                    var dict = t.IsBlockedPath ? CrossZoneBlocked : CrossZoneDirect;
                    if (!dict.ContainsKey(t.Scene!))
                        dict[t.Scene!] = t;
                }
            }
        }
    }
}
