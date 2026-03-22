using AdventureGuide.Data;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Resolves quest steps to navigation targets and manages the active
/// navigation state. Prefers live NPC positions when available, falls
/// back to static spawn data from the guide JSON.
/// </summary>
public sealed class NavigationController
{
    private readonly GuideData _data;

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

    public NavigationController(GuideData data)
    {
        _data = data;
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
            var livePos = FindLiveNPC(step.TargetName);
            if (livePos.HasValue)
            {
                Target = MakeTarget(
                    NavigationTarget.Kind.Character,
                    livePos.Value,
                    step.TargetName ?? step.Description,
                    currentScene,
                    quest.DBName, step.Order,
                    step.TargetKey);
                return true;
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
        Distance = 0f;
        Direction = Vector3.zero;
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

        // Same zone: try to upgrade to live NPC position
        if (Target.TargetKind == NavigationTarget.Kind.Character)
        {
            var livePos = FindLiveNPC(Target.DisplayName);
            if (livePos.HasValue)
            {
                Target = MakeTarget(
                    Target.TargetKind, livePos.Value,
                    Target.DisplayName, Target.Scene,
                    Target.QuestDBName, Target.StepOrder,
                    Target.TargetKey);
            }
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

        var zoneLine = FindClosestZoneLine(destZoneKey, currentScene);
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

        // Try drop/vendor sources — these are NPCs we can navigate to
        foreach (var src in item.Sources)
        {
            if (src.Type is not "drop" and not "vendor" || src.Name == null)
                continue;

            var spawn = FindSpawnByCharacterName(src.Name, currentScene);
            if (spawn == null) continue;

            Target = MakeTarget(
                NavigationTarget.Kind.Character,
                new Vector3(spawn.X, spawn.Y, spawn.Z),
                src.Name,
                spawn.Scene,
                quest.DBName, step.Order);
            return true;
        }

        // Fallback: navigate to the zone where the first source lives
        var firstZone = item.Sources[0].Zone;
        if (firstZone == null) return false;

        string? zoneKey = FindZoneKeyByDisplayName(firstZone);
        if (zoneKey == null) return false;

        var zl = FindClosestZoneLine(zoneKey, currentScene);
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
        var targetZoneKey = FindZoneKeyBySceneName(Target!.Scene);

        // Prefer a zone line leading directly to the target's zone
        var directLine = targetZoneKey != null
            ? FindClosestZoneLine(targetZoneKey, currentScene)
            : null;

        // Fallback: closest zone line in the current scene (heuristic)
        var bestLine = directLine ?? FindClosestZoneLineInScene(currentScene, playerPos);

        if (bestLine != null)
        {
            ZoneLineWaypoint = MakeTarget(
                NavigationTarget.Kind.ZoneLine,
                new Vector3(bestLine.X, bestLine.Y, bestLine.Z),
                $"To {bestLine.DestinationDisplay}",
                currentScene,
                Target.QuestDBName, Target.StepOrder);

            UpdateDistanceAndDirection(ZoneLineWaypoint.Position, playerPos);
        }
        else
        {
            // No zone line found — point directly at the target
            UpdateDistanceAndDirection(Target.Position, playerPos);
        }
    }

    // ── Spawn resolution ───────────────────────────────────────────

    /// <summary>
    /// Pick the closest spawn in the current scene, or the first spawn overall.
    /// </summary>
    private Data.SpawnPoint PickBestSpawn(List<Data.SpawnPoint> spawns, string currentScene)
    {
        var playerPos = GetPlayerPosition();
        Data.SpawnPoint? best = null;
        float bestDist = float.MaxValue;

        foreach (var sp in spawns)
        {
            if (!string.Equals(sp.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;

            if (playerPos.HasValue)
            {
                float dist = Vector3.Distance(playerPos.Value, new Vector3(sp.X, sp.Y, sp.Z));
                if (dist < bestDist) { bestDist = dist; best = sp; }
            }
            else
            {
                best ??= sp;
            }
        }

        return best ?? spawns[0];
    }

    /// <summary>
    /// Find a spawn point for a character by display name using the
    /// prebuilt CharacterNameToKeys reverse index.
    /// </summary>
    private Data.SpawnPoint? FindSpawnByCharacterName(string displayName, string currentScene)
    {
        if (!_data.CharacterNameToKeys.TryGetValue(displayName, out var keys))
            return null;

        foreach (var key in keys)
        {
            if (!_data.CharacterSpawns.TryGetValue(key, out var spawns) || spawns.Count == 0)
                continue;

            // Prefer current-zone spawn
            foreach (var sp in spawns)
            {
                if (string.Equals(sp.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                    return sp;
            }

            // Any spawn is acceptable
            return spawns[0];
        }

        return null;
    }

    // ── Zone line helpers ──────────────────────────────────────────

    private ZoneLineEntry? FindClosestZoneLine(string destinationZoneKey, string currentScene)
    {
        var playerPos = GetPlayerPosition();
        ZoneLineEntry? best = null;
        float bestDist = float.MaxValue;

        foreach (var zl in _data.ZoneLines)
        {
            if (!string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            if (!string.Equals(zl.DestinationZoneKey, destinationZoneKey, System.StringComparison.OrdinalIgnoreCase))
                continue;

            if (playerPos.HasValue)
            {
                float dist = Vector3.Distance(playerPos.Value, new Vector3(zl.X, zl.Y, zl.Z));
                if (dist < bestDist) { bestDist = dist; best = zl; }
            }
            else
            {
                best ??= zl;
            }
        }

        return best;
    }

    private ZoneLineEntry? FindClosestZoneLineInScene(string currentScene, Vector3 playerPos)
    {
        ZoneLineEntry? best = null;
        float bestDist = float.MaxValue;

        foreach (var zl in _data.ZoneLines)
        {
            if (!string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
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

    // ── Live NPC lookup ────────────────────────────────────────────

    /// <summary>
    /// Scan NPCTable.LiveNPCs for a living NPC matching the display name.
    /// Returns its current world position, or null if not found.
    /// </summary>
    private static Vector3? FindLiveNPC(string? displayName)
    {
        if (displayName == null || NPCTable.LiveNPCs == null)
            return null;

        foreach (var npc in NPCTable.LiveNPCs)
        {
            if (npc == null || npc.gameObject == null) continue;
            if (!string.Equals(npc.NPCName, displayName, System.StringComparison.OrdinalIgnoreCase))
                continue;
            var character = npc.GetComponent<Character>();
            if (character == null || !character.Alive) continue;
            return npc.transform.position;
        }

        return null;
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
