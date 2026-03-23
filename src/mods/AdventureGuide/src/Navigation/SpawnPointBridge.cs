using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Bridges static spawn data (from quest-guide.json) to live game SpawnPoint
/// objects. On each scene rebuild, indexes all SpawnPoints by their rounded
/// position for O(1) lookup. Also provides fallback for directly-placed NPCs
/// (no SpawnPoint) via NPCTable.LiveNPCs.
///
/// The static spawn positions match SpawnPoint.transform.position exactly at
/// 2-decimal precision (Vector3.ToString format). Zero position collisions
/// at 0.5m across all tested scenes.
/// </summary>
public sealed class SpawnPointBridge
{
    /// <summary>State of a spawn point for marker decisions.</summary>
    public enum SpawnState
    {
        /// <summary>NPC is alive and present at the spawn point.</summary>
        Alive,
        /// <summary>NPC died and is respawning (timer running).</summary>
        Dead,
        /// <summary>Night-only spawn during daytime hours.</summary>
        NightLocked,
        /// <summary>Spawn blocked by incomplete quest requirement.</summary>
        QuestGated,
        /// <summary>Directly-placed NPC that died — respawns on zone re-entry.</summary>
        DirectlyPlacedDead,
        /// <summary>No live SpawnPoint and NPC not found in scene.</summary>
        NotFound,
    }

    /// <summary>Result of a spawn point lookup with live state.</summary>
    public readonly struct SpawnInfo
    {
        public readonly SpawnState State;
        public readonly SpawnPoint? LiveSpawnPoint;
        public readonly float RespawnSeconds;

        public SpawnInfo(SpawnState state, SpawnPoint? liveSP = null, float respawnSeconds = 0f)
        {
            State = state;
            LiveSpawnPoint = liveSP;
            RespawnSeconds = respawnSeconds;
        }
    }

    // Position key: rounded to centimeter precision for exact matching.
    // Using a struct key avoids string allocation per lookup.
    private readonly struct PosKey : System.IEquatable<PosKey>
    {
        private readonly int _x, _y, _z;

        public PosKey(float x, float y, float z)
        {
            _x = Mathf.RoundToInt(x * 100f);
            _y = Mathf.RoundToInt(y * 100f);
            _z = Mathf.RoundToInt(z * 100f);
        }

        public bool Equals(PosKey other) => _x == other._x && _y == other._y && _z == other._z;
        public override bool Equals(object? obj) => obj is PosKey other && Equals(other);
        public override int GetHashCode() => (_x * 397) ^ (_y * 17) ^ _z;
    }

    private readonly Dictionary<PosKey, SpawnPoint> _index = new();

    /// <summary>
    /// Rebuild the index from the current scene's SpawnPoints.
    /// Call on scene change, before marker rebuild.
    /// </summary>
    public void Rebuild()
    {
        _index.Clear();

        if (SpawnPointManager.SpawnPointsInScene == null)
            return;

        foreach (var sp in SpawnPointManager.SpawnPointsInScene)
        {
            if (sp == null) continue;
            var pos = sp.transform.position;
            var key = new PosKey(pos.x, pos.y, pos.z);
            // First SpawnPoint at a position wins (collisions not expected)
            _index.TryAdd(key, sp);
        }
    }

    /// <summary>
    /// Look up the live state for a static spawn at the given position.
    /// Returns the spawn state and live SpawnPoint reference (if found).
    /// </summary>
    public SpawnInfo GetState(float x, float y, float z, string expectedNPCName)
    {
        var key = new PosKey(x, y, z);

        if (_index.TryGetValue(key, out var sp))
            return ClassifySpawnPoint(sp, expectedNPCName);

        // No SpawnPoint at this position — directly-placed NPC.
        // Check if the NPC is alive in NPCTable.LiveNPCs at this exact position.
        if (FindDirectlyPlacedNPC(x, y, z) != null)
            return new SpawnInfo(SpawnState.Alive);

        return new SpawnInfo(SpawnState.DirectlyPlacedDead);
    }

    /// <summary>
    /// Check if a specific NPC name is alive at a SpawnPoint, accounting for
    /// rare/common spawn variants. Returns true when the spawned NPC's name
    /// matches the expected quest target.
    /// </summary>
    public static bool IsExpectedNPCAlive(SpawnPoint sp, string expectedName)
    {
        return sp.MyNPCAlive
            && sp.SpawnedNPC != null
            && string.Equals(sp.SpawnedNPC.NPCName, expectedName,
                System.StringComparison.OrdinalIgnoreCase);
    }

    private static SpawnInfo ClassifySpawnPoint(SpawnPoint sp, string expectedNPCName)
    {
        // Quest-gated: can't spawn yet
        if (!sp.canSpawn)
            return new SpawnInfo(SpawnState.QuestGated, sp);

        // Night-locked: night-only spawn during daytime
        if (sp.NightSpawn && !IsNightHours())
        {
            // NPC might still be alive in the 04:00-06:59 transition window
            if (IsExpectedNPCAlive(sp, expectedNPCName))
                return new SpawnInfo(SpawnState.Alive, sp);

            return new SpawnInfo(SpawnState.NightLocked, sp);
        }

        // Alive with expected NPC
        if (IsExpectedNPCAlive(sp, expectedNPCName))
            return new SpawnInfo(SpawnState.Alive, sp);

        // Alive but wrong NPC (rare/common mismatch) — treat as not found
        // for this particular quest target. Also handles stale MyNPCAlive
        // where the reference was lost (SpawnedNPC null after zone reload).
        if (sp.MyNPCAlive && sp.SpawnedNPC != null)
            return new SpawnInfo(SpawnState.NotFound, sp);

        // Dead, respawning
        float tickRate = 60f * GetSpawnTimeMod();
        float seconds = tickRate > 0f ? sp.actualSpawnDelay / tickRate : 0f;
        return new SpawnInfo(SpawnState.Dead, sp, seconds);
    }

    /// <summary>Night spawn window: hour > 22 OR hour &lt; 4.</summary>
    private static bool IsNightHours()
    {
        int hour = GameData.Time.GetHour();
        return hour > 22 || hour < 4;
    }

    /// <summary>
    /// Scan NPCTable.LiveNPCs for a living NPC at the exact static position.
    /// Directly-placed NPCs don't wander, so their transform.position matches.
    /// </summary>
    private static NPC? FindDirectlyPlacedNPC(float x, float y, float z)
    {
        if (NPCTable.LiveNPCs == null) return null;

        var target = new PosKey(x, y, z);
        foreach (var npc in NPCTable.LiveNPCs)
        {
            if (npc == null) continue;
            var pos = npc.transform.position;
            if (target.Equals(new PosKey(pos.x, pos.y, pos.z)))
                return npc;
        }
        return null;
    }

    private static float GetSpawnTimeMod()
    {
        var gm = GameData.GM;
        return gm != null ? gm.SpawnTimeMod : 1f;
    }
}
