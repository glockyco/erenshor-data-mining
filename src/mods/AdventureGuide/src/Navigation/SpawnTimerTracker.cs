using System.Reflection;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Tracks respawn timers for quest-relevant NPCs by holding references to
/// their SpawnPoint components. When an NPC dies, the tracker records its
/// SpawnPoint (accessed via NPC.MySpawnPoint, a private field). The
/// SpawnPoint's actualSpawnDelay ticks down in the game's Update loop,
/// so we read it live — no need to maintain our own countdown.
///
/// Also detects night-only spawn points (SpawnPoint.NightSpawn) and
/// reports whether the current time-of-day allows spawning.
/// </summary>
public sealed class SpawnTimerTracker
{
    // NPC.MySpawnPoint is private — cache the FieldInfo for reflection
    private static readonly FieldInfo? MySpawnPointField =
        typeof(NPC).GetField("MySpawnPoint", BindingFlags.NonPublic | BindingFlags.Instance);

    // SpawnPoint keyed by its scene-unique ID (set in SpawnPoint.Start)
    private readonly Dictionary<string, TrackedSpawn> _tracked = new();

    /// <summary>
    /// Call when a quest-relevant NPC dies. Records the SpawnPoint for
    /// timer tracking. If the NPC's SpawnPoint cannot be resolved, this
    /// is a no-op.
    /// </summary>
    public void OnNPCDeath(NPC npc)
    {
        var sp = GetSpawnPoint(npc);
        if (sp == null || string.IsNullOrEmpty(sp.ID)) return;

        var key = EntityRegistry.DeriveStableKey(npc, sp);
        _tracked[sp.ID] = new TrackedSpawn(sp, npc.NPCName, key);
    }

    /// <summary>
    /// Call when an NPC spawns at a SpawnPoint. Removes any tracked
    /// respawn timer for that spawn point.
    /// </summary>
    public void OnNPCSpawn(SpawnPoint sp)
    {
        if (sp != null && !string.IsNullOrEmpty(sp.ID))
            _tracked.Remove(sp.ID);
    }

    /// <summary>Clear all tracked timers. Called on scene transition.</summary>
    public void Clear() => _tracked.Clear();

    /// <summary>
    /// Get remaining real seconds until respawn, or null if not tracked.
    /// Reads SpawnPoint.actualSpawnDelay live and divides by the current
    /// tick rate (60 * SpawnTimeMod).
    /// </summary>
    public float? GetRemainingSeconds(SpawnPoint sp)
    {
        if (sp == null || string.IsNullOrEmpty(sp.ID)) return null;
        if (!_tracked.ContainsKey(sp.ID)) return null;

        float tickRate = 60f * GetSpawnTimeMod();
        if (tickRate <= 0f) return null;

        return sp.actualSpawnDelay / tickRate;
    }

    /// <summary>
    /// Check if a SpawnPoint is a night-only spawn that cannot currently
    /// spawn because it's daytime.
    /// </summary>
    public static bool IsNightLocked(SpawnPoint sp)
    {
        if (!sp.NightSpawn) return false;
        int hour = GameData.Time.GetHour();
        // Spawn window: hour > 22 OR hour < 4
        return !(hour > 22 || hour < 4);
    }

    /// <summary>
    /// Format remaining seconds as ~M:SS string.
    /// </summary>
    public static string FormatTimer(float seconds)
    {
        if (seconds <= 0f) return "~0:00";
        int totalSec = Mathf.CeilToInt(seconds);
        int min = totalSec / 60;
        int sec = totalSec % 60;
        return $"~{min}:{sec:D2}";
    }

    /// <summary>All currently tracked dead spawn points.</summary>
    public IReadOnlyDictionary<string, TrackedSpawn> Tracked => _tracked;

    private static SpawnPoint? GetSpawnPoint(NPC npc)
    {
        if (MySpawnPointField == null) return null;
        return MySpawnPointField.GetValue(npc) as SpawnPoint;
    }

    private static float GetSpawnTimeMod()
    {
        var gm = GameData.GM;
        if (gm == null) return 1f;
        // SpawnTimeMod is set in GameManager.Update based on group size
        return gm.SpawnTimeMod;
    }
}

/// <summary>
/// A tracked spawn point with its NPC identity for marker labeling
/// and stable key for precise matching.
/// </summary>
public readonly struct TrackedSpawn
{
    public readonly SpawnPoint Point;
    public readonly string NPCName;
    public readonly string? StableKey;

    public TrackedSpawn(SpawnPoint point, string npcName, string? stableKey)
    {
        Point = point;
        NPCName = npcName;
        StableKey = stableKey;
    }
}
