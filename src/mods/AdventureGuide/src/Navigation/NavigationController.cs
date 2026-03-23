using AdventureGuide.Data;
using AdventureGuide.State;
using UnityEngine;
using UnityEngine.AI;

namespace AdventureGuide.Navigation;

/// <summary>
/// Resolves quest steps to navigation targets and manages the active
/// navigation state. Uses EntityRegistry for O(1) live NPC lookups
/// (closest alive NPC by display name), falling back to static spawn
/// data from the guide JSON.
/// </summary>
public sealed class NavigationController
{
    private readonly GuideData _data;
    private readonly EntityRegistry _entities;
    private readonly QuestStateTracker _state;
    private readonly SpawnTimerTracker _timers;
    private readonly MiningNodeTracker _miningTracker;
    private readonly ZoneGraph _zoneGraph;
    // Cache to avoid per-frame zone line waypoint allocation and reachability checks
    private ZoneLineEntry? _cachedZoneLine;
    private ZoneLineEntry? _pinnedZoneLine; // manual override from UI, cleared on nav change
    private Vector3 _lastCrossZoneCalcPos;
    private const float CrossZoneRecalcDistance = 10f;

    // Scratch path for reachability checks — avoids allocation per candidate
    private readonly NavMeshPath _scratchPath = new();

    /// <summary>Currently active navigation target, or null if not navigating.</summary>
    public NavigationTarget? Target { get; private set; }

    /// <summary>Distance from player to current target. Updated each frame via Update().</summary>
    public float Distance { get; private set; }

    /// <summary>World-space direction from player to target (normalized). Zero if no target.</summary>
    public Vector3 Direction { get; private set; }

    /// <summary>
    /// When navigating cross-zone, this holds the zone line we're routing through.
    /// Null when navigating within the current zone.
    /// </summary>
    public NavigationTarget? ZoneLineWaypoint { get; private set; }

    public NavigationController(GuideData data, EntityRegistry entities, QuestStateTracker state, SpawnTimerTracker timers, MiningNodeTracker miningTracker)
    {
        _data = data;
        _entities = entities;
        _state = state;
        _timers = timers;
        _miningTracker = miningTracker;
        _zoneGraph = new ZoneGraph(data, state);
    }

    /// <summary>
    /// Set navigation target from a quest step. Resolves the step's target_key
    /// to a world position using character spawns and zone line data.
    /// Returns true if a valid target was found.
    /// </summary>
    public bool NavigateTo(QuestStep step, QuestEntry quest, string currentScene)
    {
        Clear();

        if (step.TargetKey == null)
            return false;

        // Try to find a live NPC first (most accurate position)
        if (step.TargetType == "character")
        {
            var playerPos = GetPlayerPosition();
            if (playerPos.HasValue)
            {
                var liveNpc = _entities.FindClosest(step.TargetName, playerPos.Value);
                if (liveNpc != null)
                {
                    Target = MakeTarget(
                        NavigationTarget.Kind.Character,
                        liveNpc.transform.position,
                        WithCharacterUnlockText(step.TargetName ?? step.Description, step.TargetKey),
                        currentScene,
                        quest.DBName, step.Order,
                        step.TargetKey);
                    return true;
                }
            }
        }

        return step.TargetType switch
        {
            "character" => ResolveCharacterTarget(step, quest, currentScene),
            "zone" => ResolveZoneTarget(step, quest, currentScene),
            "item" => ResolveItemTarget(step, quest, currentScene),
            _ => false,
        };
    }

    /// <summary>Clear active navigation.</summary>
    /// <summary>Pin a specific zone line for cross-zone routing, overriding auto-selection.</summary>
    public void PinZoneLine(ZoneLineEntry zoneLine)
    {
        _pinnedZoneLine = zoneLine;
        // Force recalculation on next update
        _cachedZoneLine = null;
        _lastCrossZoneCalcPos = Vector3.zero;
    }

    public void Clear()
    {
        Target = null;
        ZoneLineWaypoint = null;
        _cachedZoneLine = null;
        _pinnedZoneLine = null;
        _lastCrossZoneCalcPos = Vector3.zero;
        Distance = 0f;
        Direction = Vector3.zero;
    }

    /// <summary>
    /// Navigate directly to a specific item source by its source_key.
    /// Used by click-to-navigate on individual source lines.
    /// </summary>
    public bool NavigateToSource(string sourceKey, string displayName,
        string? sourceScene, string questDBName, int stepOrder, string currentScene)
    {
        Clear();

        if (!_data.CharacterSpawns.TryGetValue(sourceKey, out var spawns) || spawns.Count == 0)
            return false;

        // Filter to the source's specific scene when available, so clicking
        // "Drops from: Stoneman · Rockshade Hold" navigates to Rockshade Hold,
        // not to an arbitrary zone where the same character type also spawns.
        var candidates = spawns;
        if (sourceScene != null)
        {
            var filtered = spawns.FindAll(s =>
                string.Equals(s.Scene, sourceScene, System.StringComparison.OrdinalIgnoreCase));
            if (filtered.Count > 0)
                candidates = filtered;
        }

        var spawn = PickBestSpawn(candidates, currentScene);
        Target = MakeTarget(
            NavigationTarget.Kind.Character,
            new Vector3(spawn.X, spawn.Y, spawn.Z),
            WithCharacterUnlockText(displayName, sourceKey),
            spawn.Scene,
            questDBName, stepOrder,
            sourceKey);
        return true;
    }

    /// <summary>
    /// Called when game state changes (quest assigned, quest completed,
    /// inventory changed, NPC killed). Re-evaluates whether the current
    /// nav step is still the active step and auto-advances if not.
    /// </summary>
    public void OnGameStateChanged(string currentScene)
    {
        _zoneGraph.Rebuild();
        if (Target == null) return;

        var quest = _data.GetByDBName(Target.QuestDBName);
        if (quest?.Steps == null)
        {
            Clear();
            return;
        }

        // Quest completed — clear nav entirely
        if (_state.IsCompleted(quest.DBName))
        {
            Clear();
            return;
        }

        // Determine which step the player is currently on
        int currentStepIdx = StepProgress.GetCurrentStepIndex(quest, _state);

        // Find the index of the step we're navigating
        int navStepIdx = -1;
        for (int i = 0; i < quest.Steps.Count; i++)
        {
            if (quest.Steps[i].Order == Target.StepOrder)
            {
                navStepIdx = i;
                break;
            }
        }

        // Nav step is still the current step or ahead of it — nothing to do
        if (navStepIdx < 0 || navStepIdx >= currentStepIdx)
            return;

        // Nav step is behind current step — advance to the first navigable
        // step at or after the current step index
        for (int i = currentStepIdx; i < quest.Steps.Count; i++)
        {
            var step = quest.Steps[i];
            if (step.TargetKey != null)
            {
                NavigateTo(step, quest, currentScene);
                return;
            }
        }

        // No more navigable steps
        Clear();
    }

    /// <summary>
    /// Call each frame. Updates distance/direction to the active target.
    /// Upgrades to live NPC position when one becomes available.
    /// Routes through zone lines for cross-zone targets.
    /// </summary>
    public void Update(string currentScene)
    {
        if (Target == null) return;

        var playerPos = GetPlayerPosition();
        if (!playerPos.HasValue) return;

        // Cross-zone: navigate to zone line instead of target directly
        if (Target.IsCrossZone(currentScene))
        {
            UpdateCrossZoneRouting(currentScene, playerPos.Value);
            return;
        }

        ZoneLineWaypoint = null;

        // Same zone: update position from closest live NPC (mutate in place)
        if (Target.TargetKind == NavigationTarget.Kind.Character)
        {
            var liveNpc = _entities.FindClosest(Target.DisplayName, playerPos.Value);
            if (liveNpc != null)
            {
                Target.Position = liveNpc.transform.position;
            }
            else
            {
                // All instances dead/mined — navigate to shortest respawn
                var bestRespawn = FindShortestRespawnPosition(Target.DisplayName);
                if (bestRespawn.HasValue)
                    Target.Position = bestRespawn.Value;
            }
        }

        UpdateDistanceAndDirection(Target.Position, playerPos.Value);
    }

    /// <summary>Check if the given quest+step is the current navigation target.</summary>
    public bool IsNavigating(string questDBName, int stepOrder) =>
        Target != null
        && Target.QuestDBName == questDBName
        && Target.StepOrder == stepOrder;

    /// <summary>
    /// Get all zone lines from the current scene to the navigation target's zone.
    /// Returns empty if not cross-zone navigating or no zone lines found.
    /// </summary>
    public List<(ZoneLineEntry line, float distance, bool isActive, bool isAccessible)> GetAlternativeZoneLines(string currentScene)
    {
        var result = new List<(ZoneLineEntry line, float distance, bool isActive, bool isAccessible)>();
        if (Target == null || !Target.IsCrossZone(currentScene))
            return result;

        var playerPos = GetPlayerPosition() ?? Vector3.zero;
        var targetZoneKey = FindZoneKeyBySceneName(Target.Scene);
        if (targetZoneKey == null) return result;

        foreach (var zl in _data.ZoneLines)
        {
            if (!string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            if (!string.Equals(zl.DestinationZoneKey, targetZoneKey, System.StringComparison.OrdinalIgnoreCase))
                continue;

            var zlPos = new Vector3(zl.X, zl.Y, zl.Z);
            float dist = Vector3.Distance(playerPos, zlPos);
            var activeZl = _pinnedZoneLine ?? _cachedZoneLine;
            bool selected = activeZl != null
                && zl.X == activeZl.X && zl.Y == activeZl.Y && zl.Z == activeZl.Z;
            bool accessible = IsZoneLineAccessible(zl);
            result.Add((zl, dist, selected, accessible));
        }

        // Accessible first, then by distance within each group
        result.Sort((a, b) =>
        {
            int cmp = b.isAccessible.CompareTo(a.isAccessible);
            return cmp != 0 ? cmp : a.distance.CompareTo(b.distance);
        });
        return result;
    }

    private Vector3? FindShortestRespawnPosition(string displayName)
    {
        // Check mining nodes first (all named "Mineral Deposit")
        if (string.Equals(displayName, "Mineral Deposit", System.StringComparison.OrdinalIgnoreCase))
        {
            var best = _miningTracker.FindShortestRespawn();
            if (best.HasValue)
                return best.Value.node.transform.position;
        }

        // Check dead enemy spawns
        SpawnPoint? bestPoint = null;
        float bestTime = float.MaxValue;
        foreach (var kvp in _timers.Tracked)
        {
            var tracked = kvp.Value;
            if (tracked.Point == null) continue;
            if (!string.Equals(tracked.NPCName, displayName, System.StringComparison.OrdinalIgnoreCase))
                continue;
            float? remaining = _timers.GetRemainingSeconds(tracked.Point);
            if (remaining.HasValue && remaining.Value < bestTime)
            {
                bestPoint = tracked.Point;
                bestTime = remaining.Value;
            }
        }

        return bestPoint?.transform.position;
    }

    // ── Target resolution ──────────────────────────────────────────

    private bool ResolveCharacterTarget(QuestStep step, QuestEntry quest, string currentScene)
    {
        if (!_data.CharacterSpawns.TryGetValue(step.TargetKey!, out var spawns) || spawns.Count == 0)
            return false;

        var spawn = PickBestSpawn(spawns, currentScene);
        Target = MakeTarget(
            NavigationTarget.Kind.Character,
            new Vector3(spawn.X, spawn.Y, spawn.Z),
            WithCharacterUnlockText(step.TargetName ?? step.Description, step.TargetKey),
            spawn.Scene,
            quest.DBName, step.Order,
            step.TargetKey);
        return true;
    }

    private bool ResolveZoneTarget(QuestStep step, QuestEntry quest, string currentScene)
    {
        // Resolve zone key from target_key or display name
        string? destZoneKey = step.TargetKey;
        if (destZoneKey != null && !_data.ZoneLookup.Values.Any(z =>
            string.Equals(z.StableKey, destZoneKey, System.StringComparison.OrdinalIgnoreCase)))
        {
            destZoneKey = FindZoneKeyByDisplayName(step.TargetName);
        }

        if (destZoneKey == null)
            return false;

        // Find the scene name for this zone
        string? destScene = null;
        foreach (var kvp in _data.ZoneLookup)
        {
            if (string.Equals(kvp.Value.StableKey, destZoneKey, System.StringComparison.OrdinalIgnoreCase))
            {
                destScene = kvp.Key;
                break;
            }
        }

        if (destScene == null)
            return false;

        // Try direct zone line first (same-scene or adjacent zone)
        var playerPos = GetPlayerPosition() ?? Vector3.zero;
        var zoneLine = FindClosestZoneLine(destZoneKey, currentScene, playerPos);

        if (zoneLine != null)
        {
            // Direct accessible route exists
            Target = MakeTarget(
                NavigationTarget.Kind.ZoneLine,
                new Vector3(zoneLine.X, zoneLine.Y, zoneLine.Z),
                $"To: {zoneLine.DestinationDisplay}",
                currentScene,
                quest.DBName, step.Order);
        }
        else
        {
            // No direct zone line — set target in the destination zone and let
            // UpdateCrossZoneRouting handle multi-hop pathfinding via ZoneGraph.
            Target = MakeTarget(
                NavigationTarget.Kind.Zone,
                Vector3.zero,
                step.TargetName ?? destScene,
                destScene,
                quest.DBName, step.Order);
        }
        return true;
    }

    private bool ResolveItemTarget(QuestStep step, QuestEntry quest, string currentScene)
    {
        // For collect/read steps: navigate to the best obtainability source
        var item = quest.RequiredItems?.Find(ri =>
            string.Equals(ri.ItemName, step.TargetName, System.StringComparison.OrdinalIgnoreCase));

        if (item?.Sources == null || item.Sources.Count == 0)
            return false;

        // Try sources with character spawn data (recursing into children)
        if (TryNavigateToAnySource(item.Sources, quest, step, currentScene))
            return true;

        // Fallback: navigate to the zone where the first source lives
        var firstScene = FindFirstScene(item.Sources);
        string? zoneKey = firstScene != null
            ? FindZoneKeyBySceneName(firstScene)
            : FindZoneKeyByDisplayName(item.Sources[0].Zone);
        if (zoneKey == null) return false;
        var zlPlayerPos = GetPlayerPosition() ?? Vector3.zero;
        var zl = FindClosestZoneLine(zoneKey, currentScene, zlPlayerPos);
        if (zl == null) return false;

        Target = MakeTarget(
            NavigationTarget.Kind.ZoneLine,
            new Vector3(zl.X, zl.Y, zl.Z),
            zl.DestinationDisplay,
            currentScene,
            quest.DBName, step.Order);
        return true;
    }

    private bool TryNavigateToAnySource(List<Data.ItemSource> sources, QuestEntry quest, QuestStep step, string currentScene)
    {
        foreach (var src in sources)
        {
            if (src.SourceKey != null
                && _data.CharacterSpawns.TryGetValue(src.SourceKey, out var spawns)
                && spawns.Count > 0)
            {
                var spawn = PickBestSpawn(spawns, currentScene);
                Target = MakeTarget(
                    NavigationTarget.Kind.Character,
                    new Vector3(spawn.X, spawn.Y, spawn.Z),
                    WithCharacterUnlockText(src.Name ?? src.SourceKey, src.SourceKey),
                    spawn.Scene,
                    quest.DBName, step.Order,
                    src.SourceKey);
                return true;
            }

            // Recurse into children
            if (src.Children != null && TryNavigateToAnySource(src.Children, quest, step, currentScene))
                return true;
        }
        return false;
    }

    // ── Cross-zone routing ─────────────────────────────────────────

    private void UpdateCrossZoneRouting(string currentScene, Vector3 playerPos)
    {
        // Only re-evaluate zone line selection when player moves significantly
        // to avoid per-frame CalculatePath calls on all zone line candidates
        bool needsRecalc = _cachedZoneLine == null
            || Vector3.Distance(_lastCrossZoneCalcPos, playerPos) > CrossZoneRecalcDistance;

        if (needsRecalc)
        {
            _lastCrossZoneCalcPos = playerPos;

            ZoneLineEntry? bestLine = null;
            bool routeIsLocked = false;

            // Manual pin takes priority over auto-selection
            if (_pinnedZoneLine != null
                && string.Equals(_pinnedZoneLine.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
            {
                bestLine = _pinnedZoneLine;
            }
            else
            {
                // Clear stale pin (wrong scene or explicitly cleared)
                _pinnedZoneLine = null;

                // Use zone graph to find the correct next hop toward the target
                var route = _zoneGraph.FindRoute(currentScene, Target!.Scene);
                var nextHopZoneKey = route?.NextHopZoneKey;

                if (nextHopZoneKey != null)
                {
                    bestLine = route!.IsLocked
                        ? FindClosestZoneLineAny(nextHopZoneKey, currentScene, playerPos)
                        : FindClosestZoneLine(nextHopZoneKey, currentScene, playerPos);
                    routeIsLocked = route.IsLocked;
                }
            }

            if (bestLine != _cachedZoneLine)
            {
                _cachedZoneLine = bestLine;
                if (bestLine != null)
                {
                    string displayText = routeIsLocked
                        ? $"To: {bestLine.DestinationDisplay}\nRequires: Complete \"{GetZoneLineLockReason(bestLine)}\""
                        : $"To: {bestLine.DestinationDisplay}";
                    ZoneLineWaypoint = MakeTarget(
                        NavigationTarget.Kind.ZoneLine,
                        new Vector3(bestLine.X, bestLine.Y, bestLine.Z),
                        displayText,
                        currentScene,
                        Target!.QuestDBName, Target.StepOrder);
                }
                else
                {
                    ZoneLineWaypoint = null;
                }
            }
        }

        if (ZoneLineWaypoint != null)
            UpdateDistanceAndDirection(ZoneLineWaypoint.Position, playerPos);
        else
            UpdateDistanceAndDirection(Target!.Position, playerPos);
    }

    // ── Spawn resolution ───────────────────────────────────────────

    /// <summary>
    /// Pick the best spawn in the current scene. Prefers fully reachable
    /// spawns (PathComplete), then partially reachable (PathPartial), then
    /// the spatially closest as a last resort.
    /// </summary>
    private Data.SpawnPoint PickBestSpawn(List<Data.SpawnPoint> spawns, string currentScene)
    {
        var playerPos = GetPlayerPosition();
        Data.SpawnPoint? bestComplete = null;  float bestCompDist = float.MaxValue;
        Data.SpawnPoint? bestPartial = null;   float bestPartDist = float.MaxValue;
        Data.SpawnPoint? bestFallback = null;   float bestFallDist = float.MaxValue;

        foreach (var sp in spawns)
        {
            if (!string.Equals(sp.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;

            if (!playerPos.HasValue) { bestComplete ??= sp; continue; }

            var spPos = new Vector3(sp.X, sp.Y, sp.Z);
            float dist = Vector3.Distance(playerPos.Value, spPos);
            var reach = GetReachability(playerPos.Value, spPos);

            if (reach == NavMeshPathStatus.PathComplete)
            {
                if (dist < bestCompDist) { bestCompDist = dist; bestComplete = sp; }
            }
            else if (reach == NavMeshPathStatus.PathPartial)
            {
                if (dist < bestPartDist) { bestPartDist = dist; bestPartial = sp; }
            }
            else
            {
                if (dist < bestFallDist) { bestFallDist = dist; bestFallback = sp; }
            }
        }

        return bestComplete ?? bestPartial ?? bestFallback ?? spawns[0];
    }

    // ── Zone line helpers ──────────────────────────────────────────

    /// <summary>
    /// Check if a zone line is accessible to the player based on quest completion.
    /// Enabled by default with no requirements = accessible. Otherwise, any unlock
    /// group being fully completed = accessible.
    /// </summary>
    private bool IsZoneLineAccessible(ZoneLineEntry zl)
    {
        if (zl.IsEnabled && (zl.RequiredQuestGroups == null || zl.RequiredQuestGroups.Count == 0))
            return true;

        if (zl.RequiredQuestGroups == null || zl.RequiredQuestGroups.Count == 0)
            return zl.IsEnabled;

        foreach (var group in zl.RequiredQuestGroups)
        {
            if (group.TrueForAll(q => _state.IsCompleted(q)))
                return true;
        }
        return false;
    }

    /// <summary>
    /// Get the display text describing why a zone line is locked.
    /// Returns the quest name(s) from the smallest incomplete unlock group.
    /// </summary>
    private string? GetZoneLineLockReason(ZoneLineEntry zl)
    {
        if (zl.RequiredQuestGroups == null || zl.RequiredQuestGroups.Count == 0)
            return null;

        // Find the smallest incomplete group (fewest quests to complete)
        List<string>? best = null;
        foreach (var group in zl.RequiredQuestGroups)
        {
            var incomplete = group.FindAll(q => !_state.IsCompleted(q));
            if (incomplete.Count == 0) return null; // group satisfied
            if (best == null || incomplete.Count < best.Count)
                best = incomplete;
        }

        if (best == null) return null;

        // Look up display names for the required quests
        var names = new System.Collections.Generic.List<string>();
        foreach (var dbName in best)
        {
            var entry = _data.GetByDBName(dbName);
            names.Add(entry?.DisplayName ?? dbName);
        }
        return string.Join(" and ", names);
    }

    private ZoneLineEntry? FindClosestZoneLine(
        string destinationZoneKey, string currentScene, Vector3 playerPos)
    {
        ZoneLineEntry? bestComplete = null;  float bestCompDist = float.MaxValue;
        ZoneLineEntry? bestPartial = null;   float bestPartDist = float.MaxValue;
        ZoneLineEntry? bestFallback = null;   float bestFallDist = float.MaxValue;

        foreach (var zl in _data.ZoneLines)
        {
            if (!string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            if (!string.Equals(zl.DestinationZoneKey, destinationZoneKey, System.StringComparison.OrdinalIgnoreCase))
                continue;
            if (!IsZoneLineAccessible(zl))
                continue;

            var zlPos = new Vector3(zl.X, zl.Y, zl.Z);
            float dist = Vector3.Distance(playerPos, zlPos);
            var reach = GetReachability(playerPos, zlPos);

            if (reach == NavMeshPathStatus.PathComplete)
            {
                if (dist < bestCompDist) { bestCompDist = dist; bestComplete = zl; }
            }
            else if (reach == NavMeshPathStatus.PathPartial)
            {
                if (dist < bestPartDist) { bestPartDist = dist; bestPartial = zl; }
            }
            else
            {
                if (dist < bestFallDist) { bestFallDist = dist; bestFallback = zl; }
            }
        }

        return bestComplete ?? bestPartial ?? bestFallback;
    }

    /// <summary>
    /// Like FindClosestZoneLine but ignores accessibility — used to find locked
    /// zone lines when no accessible route exists, for directional guidance.
    /// </summary>
    private ZoneLineEntry? FindClosestZoneLineAny(
        string destinationZoneKey, string currentScene, Vector3 playerPos)
    {
        ZoneLineEntry? best = null;
        float bestDist = float.MaxValue;

        foreach (var zl in _data.ZoneLines)
        {
            if (!string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            if (!string.Equals(zl.DestinationZoneKey, destinationZoneKey, System.StringComparison.OrdinalIgnoreCase))
                continue;

            float dist = Vector3.Distance(playerPos, new Vector3(zl.X, zl.Y, zl.Z));
            if (dist < bestDist) { bestDist = dist; best = zl; }
        }
        return best;
    }


    private bool HasZoneLineForDestination(string? zoneKey, string currentScene)
    {
        if (zoneKey == null) return false;
        foreach (var zl in _data.ZoneLines)
        {
            if (string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase)
                && string.Equals(zl.DestinationZoneKey, zoneKey, System.StringComparison.OrdinalIgnoreCase)
                && IsZoneLineAccessible(zl))
                return true;
        }
        return false;
    }

    // ── Zone key resolution ────────────────────────────────────────

    private string? FindZoneKeyBySceneName(string sceneName)
    {
        return _data.ZoneLookup.TryGetValue(sceneName, out var info) ? info.StableKey : null;
    }

    private string? FindZoneKeyByDisplayName(string? displayName)
    {
        if (displayName == null) return null;
        foreach (var kvp in _data.ZoneLookup)
        {
            if (string.Equals(kvp.Value.DisplayName, displayName, System.StringComparison.OrdinalIgnoreCase))
                return kvp.Value.StableKey;
        }
        return null;
    }

    private static string? FindFirstScene(List<Data.ItemSource> sources)
    {
        foreach (var src in sources)
        {
            if (src.Scene != null) return src.Scene;
            if (src.Children != null)
            {
                var childScene = FindFirstScene(src.Children);
                if (childScene != null) return childScene;
            }
        }
        return null;
    }


    // ── Reachability ────────────────────────────────────────────────────

    /// <summary>
    /// Classify a target's reachability: Complete (fully connected path),
    /// Partial (path exists but doesn't reach the exact point), or Invalid
    /// (no NavMesh connection at all). Both positions are snapped to the
    /// NavMesh surface before testing.
    /// </summary>
    private NavMeshPathStatus GetReachability(Vector3 from, Vector3 to)
    {
        if (!NavMesh.SamplePosition(from, out var fromHit, 5f, NavMesh.AllAreas))
            return NavMeshPathStatus.PathInvalid;
        if (!NavMesh.SamplePosition(to, out var toHit, 5f, NavMesh.AllAreas))
            return NavMeshPathStatus.PathInvalid;

        _scratchPath.ClearCorners();
        NavMesh.CalculatePath(fromHit.position, toHit.position, NavMesh.AllAreas, _scratchPath);
        return _scratchPath.status;
    }

    // ── Utilities ──────────────────────────────────────────────────

    private void UpdateDistanceAndDirection(Vector3 targetPos, Vector3 playerPos)
    {
        var delta = targetPos - playerPos;
        Distance = delta.magnitude;
        Direction = Distance > 0.1f ? delta.normalized : Vector3.zero;
    }

    private static Vector3? GetPlayerPosition()
    {
        var pc = GameData.PlayerControl;
        return pc != null ? pc.transform.position : null;
    }

    /// <summary>
    /// If a character has unmet quest unlock requirements, append a
    /// "Requires: Complete ..." line to the display name for the arrow.
    /// </summary>
    private string WithCharacterUnlockText(string displayName, string? targetKey)
    {
        if (targetKey == null) return displayName;
        if (!_data.CharacterQuestUnlocks.TryGetValue(targetKey, out var groups))
            return displayName;

        // Find smallest incomplete group
        List<string>? best = null;
        foreach (var group in groups)
        {
            var incomplete = group.FindAll(q => !_state.IsCompleted(q));
            if (incomplete.Count == 0) return displayName; // group satisfied, NPC available
            if (best == null || incomplete.Count < best.Count)
                best = incomplete;
        }

        if (best == null) return displayName;

        var names = new System.Collections.Generic.List<string>();
        foreach (var dbName in best)
        {
            var entry = _data.GetByDBName(dbName);
            names.Add(entry?.DisplayName ?? dbName);
        }
        return $"{displayName}\nRequires: Complete \"{string.Join("\" and \"", names)}\"";
    }

    private static NavigationTarget MakeTarget(
        NavigationTarget.Kind kind, Vector3 position, string displayName,
        string scene, string questDBName, int stepOrder, string? targetKey = null)
    {
        return new NavigationTarget(kind, position, displayName, scene, questDBName, stepOrder, targetKey);
    }
}
