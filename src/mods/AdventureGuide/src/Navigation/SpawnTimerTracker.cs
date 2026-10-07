using System.Reflection;

namespace AdventureGuide.Navigation;

/// <summary>
/// Tracks the SpawnPoints of NPCs that died during this scene visit, so
/// navigation can point at the spawn of a dead target that returns soonest.
/// When an NPC dies, the tracker records its SpawnPoint (accessed via
/// NPC.MySpawnPoint, a private field). The SpawnPoint's actualSpawnDelay
/// ticks down in the game's Update loop, so we read it live — no need to
/// maintain our own timer.
/// </summary>
public sealed class SpawnTimerTracker
{
    // NPC.MySpawnPoint is private — cache the FieldInfo for reflection
    private static readonly FieldInfo? MySpawnPointField = typeof(NPC).GetField(
        "MySpawnPoint",
        BindingFlags.NonPublic | BindingFlags.Instance
    );

    // SpawnPoint keyed by its scene-unique ID (set in SpawnPoint.Start)
    private readonly Dictionary<string, TrackedSpawn> _tracked = new();

    /// <summary>
    /// Call when an NPC dies. Records its SpawnPoint for timer tracking. If
    /// the NPC's SpawnPoint cannot be resolved, this is a no-op.
    /// </summary>
    public void OnNPCDeath(NPC npc)
    {
        var sp = GetSpawnPoint(npc);
        if (sp == null || string.IsNullOrEmpty(sp.ID))
            return;

        var key = EntityRegistry.DeriveStableKey(npc, sp);
        _tracked[sp.ID] = new TrackedSpawn(sp, key);
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
    /// The tracked SpawnPoint of a character that respawns soonest, or null.
    /// Navigation calls this every frame while its target is dead.
    /// </summary>
    public SpawnPoint? FindSoonestRespawn(string stableKey)
    {
        SpawnPoint? best = null;
        float bestSeconds = float.MaxValue;
        foreach (var tracked in _tracked.Values)
        {
            if (
                tracked.Point == null
                || !string.Equals(
                    tracked.StableKey,
                    stableKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
                continue;
            float seconds = SpawnPointBridge.GetRespawnSeconds(tracked.Point);
            if (seconds < bestSeconds)
            {
                best = tracked.Point;
                bestSeconds = seconds;
            }
        }
        return best;
    }

    private static SpawnPoint? GetSpawnPoint(NPC npc)
    {
        if (MySpawnPointField == null)
            return null;
        return MySpawnPointField.GetValue(npc) as SpawnPoint;
    }
}

/// <summary>A tracked spawn point with the stable key of the NPC that died there.</summary>
internal readonly struct TrackedSpawn
{
    public readonly SpawnPoint Point;
    public readonly string? StableKey;

    public TrackedSpawn(SpawnPoint point, string? stableKey)
    {
        Point = point;
        StableKey = stableKey;
    }
}
