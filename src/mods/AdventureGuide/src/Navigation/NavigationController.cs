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
    // Cache to avoid per-frame zone line waypoint allocation and reachability checks
    private ZoneLineEntry? _cachedZoneLine;
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

    public NavigationController(GuideData data, EntityRegistry entities, QuestStateTracker state)
    {
        _data = data;
        _entities = entities;
        _state = state;
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
                        step.TargetName ?? step.Description,
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
    public void Clear()
    {
        Target = null;
        ZoneLineWaypoint = null;
        _cachedZoneLine = null;
        _lastCrossZoneCalcPos = Vector3.zero;
        Distance = 0f;
        Direction = Vector3.zero;
    }

    /// <summary>
    /// Called when game state changes (quest assigned, quest completed,
    /// inventory changed, NPC killed). Re-evaluates whether the current
    /// nav step is still the active step and auto-advances if not.
    /// </summary>
    public void OnGameStateChanged(string currentScene)
    {
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
                Target.Position = liveNpc.transform.position;
        }

        UpdateDistanceAndDirection(Target.Position, playerPos.Value);
    }

    /// <summary>Check if the given quest+step is the current navigation target.</summary>
    public bool IsNavigating(string questDBName, int stepOrder) =>
        Target != null
        && Target.QuestDBName == questDBName
        && Target.StepOrder == stepOrder;

    // ── Target resolution ──────────────────────────────────────────

    private bool ResolveCharacterTarget(QuestStep step, QuestEntry quest, string currentScene)
    {
        if (!_data.CharacterSpawns.TryGetValue(step.TargetKey!, out var spawns) || spawns.Count == 0)
            return false;

        var spawn = PickBestSpawn(spawns, currentScene);
        Target = MakeTarget(
            NavigationTarget.Kind.Character,
            new Vector3(spawn.X, spawn.Y, spawn.Z),
            step.TargetName ?? step.Description,
            spawn.Scene,
            quest.DBName, step.Order,
            step.TargetKey);
        return true;
    }

    private bool ResolveZoneTarget(QuestStep step, QuestEntry quest, string currentScene)
    {
        // Find zone stable key: try target_key directly, then search zone lookup
        string? destZoneKey = step.TargetKey;

        // If target_key doesn't match a zone line destination, search by display name
        if (!HasZoneLineForDestination(destZoneKey, currentScene))
        {
            destZoneKey = FindZoneKeyByDisplayName(step.TargetName);
        }

        if (destZoneKey == null)
            return false;

        var playerPos = GetPlayerPosition() ?? Vector3.zero;
        var zoneLine = FindClosestZoneLine(destZoneKey, currentScene, playerPos);
        if (zoneLine == null)
            return false;

        Target = MakeTarget(
            NavigationTarget.Kind.ZoneLine,
            new Vector3(zoneLine.X, zoneLine.Y, zoneLine.Z),
            zoneLine.DestinationDisplay,
            currentScene,
            quest.DBName, step.Order);
        return true;
    }

    private bool ResolveItemTarget(QuestStep step, QuestEntry quest, string currentScene)
    {
        // For collect/read steps: navigate to the best obtainability source
        var item = quest.RequiredItems?.Find(ri =>
            string.Equals(ri.ItemName, step.TargetName, System.StringComparison.OrdinalIgnoreCase));

        if (item?.Sources == null || item.Sources.Count == 0)
            return false;

        // Try sources with character spawn data
        foreach (var src in item.Sources)
        {
            if (src.SourceKey == null) continue;

            if (!_data.CharacterSpawns.TryGetValue(src.SourceKey, out var spawns) || spawns.Count == 0)
                continue;

            var spawn = PickBestSpawn(spawns, currentScene);
            Target = MakeTarget(
                NavigationTarget.Kind.Character,
                new Vector3(spawn.X, spawn.Y, spawn.Z),
                src.Name ?? src.SourceKey,
                spawn.Scene,
                quest.DBName, step.Order,
                src.SourceKey);
            return true;
        }

        // Fallback: navigate to the zone where the first source lives
        var firstZone = item.Sources[0].Zone;
        if (firstZone == null) return false;

        string? zoneKey = FindZoneKeyByDisplayName(firstZone);
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
            var targetZoneKey = FindZoneKeyBySceneName(Target!.Scene);

            var directLine = targetZoneKey != null
                ? FindClosestZoneLine(targetZoneKey, currentScene, playerPos)
                : null;

            var bestLine = directLine ?? FindClosestZoneLineInScene(currentScene, playerPos);

            if (bestLine != _cachedZoneLine)
            {
                _cachedZoneLine = bestLine;
                if (bestLine != null)
                {
                    ZoneLineWaypoint = MakeTarget(
                        NavigationTarget.Kind.ZoneLine,
                        new Vector3(bestLine.X, bestLine.Y, bestLine.Z),
                        $"To {bestLine.DestinationDisplay}",
                        currentScene,
                        Target.QuestDBName, Target.StepOrder);
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

    private ZoneLineEntry? FindClosestZoneLineInScene(string currentScene, Vector3 playerPos)
    {
        ZoneLineEntry? bestComplete = null;  float bestCompDist = float.MaxValue;
        ZoneLineEntry? bestPartial = null;   float bestPartDist = float.MaxValue;
        ZoneLineEntry? bestFallback = null;   float bestFallDist = float.MaxValue;

        foreach (var zl in _data.ZoneLines)
        {
            if (!string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
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

    private bool HasZoneLineForDestination(string? zoneKey, string currentScene)
    {
        if (zoneKey == null) return false;
        foreach (var zl in _data.ZoneLines)
        {
            if (string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase)
                && string.Equals(zl.DestinationZoneKey, zoneKey, System.StringComparison.OrdinalIgnoreCase))
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

    private static NavigationTarget MakeTarget(
        NavigationTarget.Kind kind, Vector3 position, string displayName,
        string scene, string questDBName, int stepOrder, string? targetKey = null)
    {
        return new NavigationTarget(kind, position, displayName, scene, questDBName, stepOrder, targetKey);
    }
}
