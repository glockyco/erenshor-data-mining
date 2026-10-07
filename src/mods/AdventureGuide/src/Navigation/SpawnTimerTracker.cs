using System.Reflection;

namespace AdventureGuide.Navigation;

/// <summary>
/// Tracks respawn timers for quest-relevant NPCs by holding references to
/// their SpawnPoint components. When an NPC dies, the tracker records its
/// SpawnPoint (accessed via NPC.MySpawnPoint, a private field). The
/// SpawnPoint's actualSpawnDelay ticks down in the game's Update loop,
/// so we read it live — no need to maintain our own timer.
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
    /// Call when a quest-relevant NPC dies. Records the SpawnPoint for
    /// timer tracking. If the NPC's SpawnPoint cannot be resolved, this
    /// is a no-op.
    /// </summary>
    public void OnNPCDeath(NPC npc)
    {
        var sp = GetSpawnPoint(npc);
        if (sp == null || string.IsNullOrEmpty(sp.ID))
            return;

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
    /// Reads SpawnPoint.actualSpawnDelay live.
    /// </summary>
    public float? GetRemainingSeconds(SpawnPoint sp)
    {
        if (sp == null || string.IsNullOrEmpty(sp.ID))
            return null;
        if (!_tracked.ContainsKey(sp.ID))
            return null;

        return SpawnPointBridge.GetRespawnSeconds(sp);
    }

    /// <summary>All currently tracked dead spawn points.</summary>
    public IReadOnlyDictionary<string, TrackedSpawn> Tracked => _tracked;

    private static SpawnPoint? GetSpawnPoint(NPC npc)
    {
        if (MySpawnPointField == null)
            return null;
        return MySpawnPointField.GetValue(npc) as SpawnPoint;
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
