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

/// Per-key best-target selection shared by <see cref="NavigationEngine"/> and
/// <c>TrackerPanel</c>.
///
/// <see cref="Tick"/> re-evaluates cached target snapshots against the current
/// player position and maintained selector snapshot set. Consumers compute
/// distance inline from <c>SelectedNavTarget.Target.X/Y/Z</c> — the struct does
/// not carry a distance snapshot.
///
/// Priority algorithm (eight tiers; "direct" means <c>IsBlockedPath</c> is false):
/// <list type="number">
///   <item>Direct + same-zone, guaranteed loot — prefer non-prerequisite targets, then closest</item>
///   <item>Direct + same-zone, actionable — prefer non-prerequisite targets, then closest</item>
///   <item>Direct + same-zone, non-actionable — prefer non-prerequisite targets, then closest</item>
///   <item>Direct + cross-zone — fewest zone hops</item>
///   <item>Blocked-path + same-zone, guaranteed loot — prefer non-prerequisite targets, then closest</item>
///   <item>Blocked-path + same-zone, actionable — prefer non-prerequisite targets, then closest</item>
///   <item>Blocked-path + same-zone, non-actionable — prefer non-prerequisite targets, then closest</item>
///   <item>Blocked-path + cross-zone — fewest zone hops</item>
/// </list>
/// TravelToZone candidates are always skipped.
public sealed class NavigationTargetSelector
{
    private const float DefaultRerankIntervalSeconds = 1f;

    private readonly ZoneRouter _router;
    private readonly CompiledGuideModel? _guide;
    private readonly INavigationSelectorLiveState? _liveState;
    private readonly DiagnosticsCore? _diagnostics;
    private readonly Dictionary<string, SelectedNavTarget> _cache = new(StringComparer.Ordinal);


    // Per-key pre-decomposed target structure. Entries are retained across forced
    // ticks so their inner lists can be cleared and refilled without reallocation.
    private readonly Dictionary<string, TargetEntry> _entries = new(StringComparer.Ordinal);

    // Scratch collections for key-set management during full rebuilds.
    private readonly HashSet<string> _activeKeys = new(StringComparer.Ordinal);
    private readonly List<string> _keysToEvict = new();
    private readonly Func<float> _clock;
    private readonly float _rerankInterval;
    private readonly Func<IReadOnlyList<QuestCostSample>>? _topQuestCostProvider;

    private NavigationTargetSnapshots? _lastSnapshots;
    private string? _lastCurrentZone;
    private float _lastRerankTime = float.NegativeInfinity;
    private DiagnosticTrigger _lastForceReason = DiagnosticTrigger.Unknown;
    private int _lastResolvedTargetCount;
    private int _lastBatchKeyCount;
    private IReadOnlyList<QuestCostSample> _topQuestCosts = Array.Empty<QuestCostSample>();

    internal NavigationTargetSelector(
        NavigationTargetResolver resolution,
        ZoneRouter router,
        CompiledGuideModel guide,
        INavigationSelectorLiveState liveState,
        DiagnosticsCore? diagnostics = null
    )
        : this(
            router,
            guide,
            liveState,
            diagnostics,
            () => UnityEngine.Time.time,
            DefaultRerankIntervalSeconds,
            () => resolution.ExportDiagnosticsSnapshot().TopQuestCosts
        ) { }

    internal NavigationTargetSelector(
        ZoneRouter router,
        CompiledGuideModel? guide = null,
        INavigationSelectorLiveState? liveState = null,
        DiagnosticsCore? diagnostics = null,
        Func<float>? clock = null,
        float rerankInterval = 0f,
        Func<IReadOnlyList<QuestCostSample>>? topQuestCostProvider = null
    )
    {
        _router = router;
        _guide = guide;
        _liveState = liveState;
        _diagnostics = diagnostics;
        _clock = clock ?? (() => 0f);
        _rerankInterval = rerankInterval;
        _topQuestCostProvider = topQuestCostProvider;
    }


/// <summary>
/// Forces the next <see cref="Tick"/> to rebuild cached targets even when the
/// engine reuses the same maintained snapshot reference.
/// </summary>
internal void InvalidateTargets()
{
    _lastSnapshots = null;
}



private bool RefreshEntries(
    NavigationTargetSnapshots snapshots,
    string currentZone,
    bool snapshotsChanged,
    bool zoneChanged,
    DiagnosticsContext context,
    long startTick)
{
    _activeKeys.Clear();
    var refreshKeys = new List<string>();
    var collectionToken = _diagnostics?.BeginSpan(
        DiagnosticSpanKind.NavSelectorCollectKeys,
        context,
        primaryKey: currentZone
    );
    long collectionStart = Stopwatch.GetTimestamp();
    try
    {
        for (int i = 0; i < snapshots.Snapshots.Count; i++)
        {
            string key = snapshots.Snapshots[i].NodeKey;
            if (!_activeKeys.Add(key))
                continue;
            refreshKeys.Add(key);
        }
    }
    finally
    {
        _lastBatchKeyCount = refreshKeys.Count;
        if (collectionToken != null)
            _diagnostics!.EndSpan(
                collectionToken.Value,
                Stopwatch.GetTimestamp() - collectionStart,
                value0: _lastBatchKeyCount,
                value1: 0
            );
    }

    bool targetsChanged = false;
    _lastResolvedTargetCount = 0;
    var batchToken = _diagnostics?.BeginSpan(
        DiagnosticSpanKind.NavSelectorBatchResolve,
        context,
        primaryKey: currentZone
    );
    long batchStart = Stopwatch.GetTimestamp();
    try
    {
        for (int i = 0; i < refreshKeys.Count; i++)
        {
            string key = refreshKeys[i];
            if (!snapshots.TryGet(key, out var snapshot))
            {
                if (_entries.Remove(key))
                    targetsChanged = true;
                continue;
            }

            var targets = snapshot.Targets;
            _lastResolvedTargetCount += targets.Count;
            if (targets.Count == 0)
            {
                if (_entries.Remove(key))
                    targetsChanged = true;
                continue;
            }

            if (!_entries.TryGetValue(key, out var entry))
            {
                entry = new TargetEntry();
                _entries[key] = entry;
                entry.Rebuild(targets, currentZone);
                targetsChanged = true;
                continue;
            }

            if (
                zoneChanged
                || !ReferenceEquals(entry.Source, targets)
                || !string.Equals(entry.CurrentZone, currentZone, StringComparison.OrdinalIgnoreCase)
            )

            {
                entry.Rebuild(targets, currentZone);
                targetsChanged = true;
            }
        }
    }
    finally
    {
        _topQuestCosts = _topQuestCostProvider?.Invoke() ?? Array.Empty<QuestCostSample>();
        if (batchToken != null)
            _diagnostics!.EndSpan(
                batchToken.Value,
                Stopwatch.GetTimestamp() - batchStart,
                value0: _lastBatchKeyCount,
                value1: _lastResolvedTargetCount
            );
    }

    _keysToEvict.Clear();
    foreach (var key in _entries.Keys)
        if (!_activeKeys.Contains(key))
            _keysToEvict.Add(key);
    foreach (var key in _keysToEvict)
    {
        _entries.Remove(key);
        targetsChanged = true;
    }

    if (targetsChanged)
    {
        var refreshContext = DiagnosticsContext.Root(
            snapshotsChanged ? DiagnosticTrigger.NavSetChanged : DiagnosticTrigger.TargetSourceVersionChanged
        );
        _lastForceReason = refreshContext.Trigger;
        _diagnostics?.RecordEvent(
            new DiagnosticEvent(
                DiagnosticEventKind.SelectorRefreshForced,
                refreshContext,
                timestampTicks: startTick,
                primaryKey: currentZone,
                value0: _entries.Count,
                value1: _lastResolvedTargetCount
            )
        );
    }

    return targetsChanged;
}

/// <summary>
/// Called once per frame by Plugin before consumers read.
///
/// Re-scores cached targets against the current player position and live-state
/// overlays. When the maintained <paramref name="snapshots"/> reference changes,
/// the selector rebuilds its per-key entries from the current resolved target
/// lists. Stable frames reuse cached entries unless live-world state or the
/// rerank interval requires another score pass.
/// </summary>
internal void Tick(
    float playerX,
    float playerY,
    float playerZ,
    string currentZone,
    NavigationTargetSnapshots snapshots,
    bool liveWorldChanged)
{
    bool liveStateChannelChanged = _liveState?.TryConsumeLiveWorldChange() ?? false;
    bool effectiveLiveWorldChanged = liveWorldChanged || liveStateChannelChanged;
    bool snapshotsChanged = !ReferenceEquals(snapshots, _lastSnapshots);
    bool zoneChanged = !string.Equals(currentZone, _lastCurrentZone, StringComparison.OrdinalIgnoreCase);
    var context = DiagnosticsContext.Root(
        snapshotsChanged ? DiagnosticTrigger.NavSetChanged : DiagnosticTrigger.Unknown
    );
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
        if (!snapshotsChanged && !zoneChanged && !effectiveLiveWorldChanged && !due)
            return;

        bool targetsChanged = RefreshEntries(
            snapshots,
            currentZone,
            snapshotsChanged,
            zoneChanged,
            context,
            startTick
        );
        if (!snapshotsChanged && !zoneChanged && !targetsChanged && !effectiveLiveWorldChanged && !due)
            return;

        _lastSnapshots = snapshots;
        _lastCurrentZone = currentZone;
        _lastRerankTime = now;
        if (zoneChanged || targetsChanged)
            _cache.Clear();


        foreach (var kv in _entries)
        {
            UpdateLivePositions(kv.Value);
            var selected = SelectBestCore(
                kv.Value,
                playerX,
                playerY,
                playerZ,
                currentZone,
                _router
            );
            if (selected.HasValue)
                _cache[kv.Key] = selected.Value;
            else
                _cache.Remove(kv.Key);
        }
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
            lastResolvedTargetCount: _lastResolvedTargetCount,
            lastBatchKeyCount: _lastBatchKeyCount,
            topQuestCosts: _topQuestCosts
        );
    }

    /// <summary>
    /// Refreshes cached same-zone target copies from canonical live-source truth.
    /// Cached copies keep selector-local scoring state in sync without mutating the
    /// shared resolution targets consumed by other systems.
    /// </summary>
    private void UpdateLivePositions(TargetEntry entry)
    {
        if (_liveState == null)
            return;

        for (int i = 0; i < entry.SameZoneMutableTargets.Count; i++)
        {
            var target = entry.SameZoneMutableTargets[i];
            var snapshot = _liveState.GetLiveSourceSnapshot(target.SourceKey, target.TargetNode.Node);
            var updatedTarget = ApplyLiveSourceSnapshot(entry.SameZoneMutableBaseTargets[i], target, snapshot);
            if (ReferenceEquals(updatedTarget, target))
                continue;

            entry.SameZoneMutableTargets[i] = updatedTarget;
            entry.SameZone[entry.SameZoneMutableIndices[i]] = updatedTarget;
        }
    }

    private ResolvedQuestTarget ApplyLiveSourceSnapshot(
        ResolvedQuestTarget baseTarget,
        ResolvedQuestTarget currentTarget,
        LiveSourceSnapshot snapshot)
    {
        if (snapshot.Kind == LiveSourceKind.Unknown)
            return baseTarget;

        var sourceNode = ResolveStaticSourceNode(baseTarget);
        switch (snapshot.Kind)
        {
            case LiveSourceKind.Character:
                return ApplyCharacterSnapshot(baseTarget, snapshot, sourceNode);
            case LiveSourceKind.MiningNode:
            case LiveSourceKind.ItemBag:
                return ApplyStaticSnapshot(baseTarget, snapshot, sourceNode);
            default:
                return currentTarget;
        }
    }

    private ResolvedQuestTarget ApplyCharacterSnapshot(
        ResolvedQuestTarget baseTarget,
        LiveSourceSnapshot snapshot,
        Node? sourceNode)
    {
        switch (snapshot.Occupancy)
        {
            case LiveSourceOccupancy.Alive:
                return BuildSnapshotTarget(baseTarget, target =>
                {
                    ApplyLivePosition(target, snapshot.LivePosition);
                    target.IsActionable = true;
                });
            case LiveSourceOccupancy.Dead:
                return BuildSnapshotTarget(
                    baseTarget,
                    target =>
                    {
                        if (snapshot.LivePosition.HasValue)
                        {
                            ApplyLivePosition(target, snapshot.LivePosition);
                        }
                        else
                        {
                            ApplyStaticPosition(target, sourceNode ?? baseTarget.TargetNode.Node);
                        }

                        bool confirmedCorpseLoot = baseTarget.IsActionable
                            && baseTarget.IsGuaranteedLoot
                            && snapshot.AnchoredLivePosition.HasValue;
                        target.IsActionable = confirmedCorpseLoot;
                    },
                    explanation: snapshot.RequiresZoneReentry
                        ? NavigationExplanationBuilder.BuildZoneReentryExplanation(baseTarget.Explanation)
                        : null,
                    isBlockedPath: baseTarget.IsBlockedPath || snapshot.RequiresZoneReentry);
            case LiveSourceOccupancy.NightLocked:
            case LiveSourceOccupancy.UnlockBlocked:
            case LiveSourceOccupancy.Disabled:
                return BuildSnapshotTarget(baseTarget, target =>
                {
                    ApplyStaticPosition(target, sourceNode ?? baseTarget.TargetNode.Node);
                    target.IsActionable = false;
                });
            default:
                return baseTarget;
        }
    }

    private ResolvedQuestTarget ApplyStaticSnapshot(
        ResolvedQuestTarget baseTarget,
        LiveSourceSnapshot snapshot,
        Node? sourceNode)
    {
        return BuildSnapshotTarget(baseTarget, target =>
        {
            ApplyStaticPosition(target, sourceNode ?? baseTarget.TargetNode.Node);
            target.IsActionable = snapshot.IsActionable;
        });
    }

    private static ResolvedQuestTarget BuildSnapshotTarget(
        ResolvedQuestTarget baseTarget,
        Action<ResolvedQuestTarget> apply,
        NavigationExplanation? explanation = null,
        bool? isBlockedPath = null)
    {
        var target = new ResolvedQuestTarget(
            baseTarget.TargetNodeKey,
            baseTarget.Scene,
            baseTarget.SourceKey,
            baseTarget.GoalNode,
            baseTarget.TargetNode,
            baseTarget.Semantic,
            explanation ?? baseTarget.Explanation,
            baseTarget.X,
            baseTarget.Y,
            baseTarget.Z,
            baseTarget.IsActionable,
            baseTarget.RequiredForQuestKey,
            isBlockedPath ?? baseTarget.IsBlockedPath,
            baseTarget.IsGuaranteedLoot,
            baseTarget.AvailabilityPriority);
        apply(target);
        return target;
    }

    private Node? ResolveStaticSourceNode(ResolvedQuestTarget target)
    {
        if (_guide == null || string.IsNullOrEmpty(target.SourceKey))
            return target.TargetNode.Node;

        return _guide.GetNode(target.SourceKey) ?? target.TargetNode.Node;
    }

    private static void ApplyLivePosition(
        ResolvedQuestTarget target,
        (float X, float Y, float Z)? position)
    {
        if (!position.HasValue)
            return;

        target.X = position.Value.X;
        target.Y = position.Value.Y;
        target.Z = position.Value.Z;
    }

    private static void ApplyStaticPosition(ResolvedQuestTarget target, Node node)
    {
        if (!node.X.HasValue || !node.Y.HasValue || !node.Z.HasValue)
            return;

        target.X = node.X.Value;
        target.Y = node.Y.Value;
        target.Z = node.Z.Value;
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
            if (!float.IsFinite(t.X) || !float.IsFinite(t.Y) || !float.IsFinite(t.Z))
                continue;
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

        public void Consider(ResolvedQuestTarget target, float distance)
        {
            if (target.IsGuaranteedLoot)
            {
                if (!target.IsBlockedPath)
                {
                    if (IsBetterCandidate(target, distance, DirectGuaranteedLoot, DirectGuaranteedLootDist))
                    {
                        DirectGuaranteedLoot = target;
                        DirectGuaranteedLootDist = distance;
                    }
                }
                else if (IsBetterCandidate(target, distance, BlockedGuaranteedLoot, BlockedGuaranteedLootDist))
                {
                    BlockedGuaranteedLoot = target;
                    BlockedGuaranteedLootDist = distance;
                }
                return;
            }

            if (!target.IsBlockedPath)
            {
                if (IsBetterCandidate(target, distance, Direct, DirectDist))
                {
                    Direct = target;
                    DirectDist = distance;
                }
            }
            else if (IsBetterCandidate(target, distance, Blocked, BlockedDist))
            {
                Blocked = target;
                BlockedDist = distance;
            }
        }

        private static bool IsBetterCandidate(
            ResolvedQuestTarget candidate,
            float candidateDistance,
            ResolvedQuestTarget? currentBest,
            float currentBestDistance
        )
        {
            if (currentBest == null)
                return true;

            if (candidate.AvailabilityPriority != currentBest.AvailabilityPriority)
                return candidate.AvailabilityPriority < currentBest.AvailabilityPriority;

            bool candidateIsDirectSource = string.IsNullOrEmpty(candidate.RequiredForQuestKey);
            bool bestIsDirectSource = string.IsNullOrEmpty(currentBest.RequiredForQuestKey);
            if (candidateIsDirectSource != bestIsDirectSource)
                return candidateIsDirectSource;

            return candidateDistance < currentBestDistance;
        }
    }

    /// <summary>
    /// Per-key pre-decomposed target structure owned by <see cref="NavigationTargetSelector"/>.
    ///
    /// Rebuilt on each forced <see cref="Tick"/>; inner collections are retained across
    /// force ticks so they can be cleared and refilled without reallocation on every
    /// live-world event. Same-zone mutable entries keep parallel references to their
    /// immutable snapshot targets so <see cref="UpdateLivePositions"/> can rebuild
    /// selector-local copies without mutating shared resolution outputs.
    /// </summary>
    private sealed class TargetEntry
    {
        /// <summary>Original snapshot targets used only for change detection.</summary>
        public IReadOnlyList<ResolvedQuestTarget> Source = Array.Empty<ResolvedQuestTarget>();

        /// <summary>Selector-owned target copies; objects are shared with the sub-lists.</summary>
        public IReadOnlyList<ResolvedQuestTarget> All = Array.Empty<ResolvedQuestTarget>();
        public string CurrentZone = string.Empty;


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
        public readonly List<ResolvedQuestTarget> SameZoneMutableBaseTargets = new();
        public readonly List<int> SameZoneMutableIndices = new();

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
            Source = all;
            All = CloneTargets(all);
            CurrentZone = currentZone;
            SameZone.Clear();

            SameZoneMutableTargets.Clear();
            SameZoneMutableBaseTargets.Clear();
            SameZoneMutableIndices.Clear();
            CrossZoneDirect.Clear();
            CrossZoneBlocked.Clear();

            for (int i = 0; i < All.Count; i++)
            {
                var t = All[i];
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
                    {
                        SameZoneMutableTargets.Add(t);
                        SameZoneMutableBaseTargets.Add(all[i]);
                        SameZoneMutableIndices.Add(SameZone.Count - 1);
                    }
                }
                else if (!string.IsNullOrEmpty(t.Scene))
                {
                    // One representative per destination zone, split by blocking.
                    var dict = t.IsBlockedPath ? CrossZoneBlocked : CrossZoneDirect;
                    if (!dict.TryGetValue(t.Scene!, out var existing)
                        || t.AvailabilityPriority < existing.AvailabilityPriority)
                        dict[t.Scene!] = t;
                }
            }
        }

        private static IReadOnlyList<ResolvedQuestTarget> CloneTargets(IReadOnlyList<ResolvedQuestTarget> targets)
        {
            if (targets.Count == 0)
                return Array.Empty<ResolvedQuestTarget>();

            var copies = new ResolvedQuestTarget[targets.Count];
            for (int i = 0; i < targets.Count; i++)
            {
                var target = targets[i];
                copies[i] = new ResolvedQuestTarget(
                    target.TargetNodeKey,
                    target.Scene,
                    target.SourceKey,
                    target.GoalNode,
                    target.TargetNode,
                    target.Semantic,
                    target.Explanation,
                    target.X,
                    target.Y,
                    target.Z,
                    target.IsActionable,
                    target.RequiredForQuestKey,
                    target.IsBlockedPath,
                    target.IsGuaranteedLoot,
                    target.AvailabilityPriority);
            }

            return copies;
        }
    }
}
