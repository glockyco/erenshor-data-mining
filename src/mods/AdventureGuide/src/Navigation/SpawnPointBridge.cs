using UnityEngine;
using AdventureGuide.Navigation;



/// <summary>
/// Bridges static spawn data (from quest-guide.json) to live game SpawnPoint
/// objects. On each scene rebuild, indexes all SpawnPoints by their rounded
/// position for O(1) lookup. For directly-placed NPCs (no SpawnPoint),
/// a name-indexed NPC cache built during Rebuild detects liveness via
/// proximity matching. Destroyed NPCs are filtered out at lookup time
/// through Unity's fake-null on destroyed GameObjects.
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
        /// <summary>Mining node has been mined and is regenerating.</summary>
        Mined,
        /// <summary>Night-only spawn during daytime hours.</summary>
        NightLocked,
        /// <summary>Spawn blocked by incomplete quest requirement.</summary>
        QuestGated,
        /// <summary>Directly-placed NPC that died — respawns on zone re-entry.</summary>
        DirectlyPlacedDead,
        /// <summary>Spawn point is disabled — requires a quest unlock to activate.</summary>
        Disabled,
        /// <summary>No live SpawnPoint and NPC not found in scene.</summary>
        NotFound,
    }

    /// <summary>Result of a spawn point lookup with live state.</summary>
    public readonly struct SpawnInfo
    {
        public readonly SpawnState State;
        public readonly SpawnPoint? LiveSpawnPoint;
        public readonly NPC? LiveNPC;
        public readonly MiningNode? LiveMiningNode;
        public readonly float RespawnSeconds;

        public SpawnInfo(SpawnState state, SpawnPoint? liveSP = null, NPC? liveNPC = null,
            MiningNode? miningNode = null, float respawnSeconds = 0f)
        {
            State = state;
            LiveSpawnPoint = liveSP;
            LiveNPC = liveNPC;
            LiveMiningNode = miningNode;
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

    // Directly-placed NPC cache: name (lowercase) → list of NPC references.
    // Built once per Rebuild from FindObjectsOfType. Destroyed NPCs become
    // Unity-null between rebuilds, filtered at lookup time.
    private readonly Dictionary<string, List<NPC>> _npcByName = new();

    /// <summary>
    /// Rebuild the index from the current scene's SpawnPoints.
    /// Call on scene change, before marker rebuild.
    /// </summary>
    public void Rebuild()
    {
        _index.Clear();
        _npcByName.Clear();

        if (SpawnPointManager.SpawnPointsInScene != null)
        {
            foreach (var sp in SpawnPointManager.SpawnPointsInScene)
            {
                if (sp == null) continue;
                var pos = sp.transform.position;
                var key = new PosKey(pos.x, pos.y, pos.z);
                // First SpawnPoint at a position wins (collisions not expected)
                _index.TryAdd(key, sp);
            }
        }

        // Cache all active NPCs by lowercase name for directly-placed lookup.
        // One FindObjectsOfType call per scene load, reused for all GetState calls.
        foreach (var npc in UnityEngine.Object.FindObjectsOfType<NPC>())
        {
            if (npc == null || string.IsNullOrEmpty(npc.NPCName)) continue;
            var nameKey = npc.NPCName.ToLowerInvariant();
            if (!_npcByName.TryGetValue(nameKey, out var list))
            {
                list = new List<NPC>();
                _npcByName[nameKey] = list;
            }
            list.Add(npc);
        }
    }

    /// <summary>
    /// Look up the live state for a spawn point from guide data.
    /// <para>
    /// Checks static flags from the guide JSON first (IsEnabled, NightSpawn),
    /// then performs the live scene lookup. Static checks allow the correct
    /// state to be returned even when the NPC is absent from the scene for a
    /// known reason (disabled by quest gate, wrong time of day).
    /// </para>
    /// </summary>
    public SpawnInfo GetState(AdventureGuide.Data.SpawnPoint staticSpawn, string expectedNPCName)
    {
        // Disabled spawn points never activate without a quest unlock.
        // Check before the scene lookup so we report the real reason.
        if (!staticSpawn.IsEnabled)
            return new SpawnInfo(SpawnState.Disabled);

        return QueryLiveState(staticSpawn.X, staticSpawn.Y, staticSpawn.Z, expectedNPCName);
    }

    private SpawnInfo QueryLiveState(float x, float y, float z, string expectedNPCName)
    {
        var key = new PosKey(x, y, z);

        if (_index.TryGetValue(key, out var sp))
            return ClassifySpawnPoint(sp, expectedNPCName);

        // No SpawnPoint at this position — directly-placed NPC.
        // Search active NPCs by name + proximity since directly-placed NPCs
        // often aren't in NPCTable.LiveNPCs and can drift from placed position.
        var npc = FindDirectlyPlacedNPC(x, y, z, expectedNPCName);
        if (npc != null)
        {
            // Mining nodes stay "alive" when mined — the NPC persists with
            // renderer and Character component disabled. Check MiningNode
            // component for the real state.
            var miningNode = npc.GetComponent<MiningNode>();
            if (miningNode != null)
            {
                if (IsMiningNodeMined(miningNode))
                {
                    float seconds = GetMiningNodeRespawnSeconds(miningNode);
                    return new SpawnInfo(SpawnState.Mined, liveNPC: npc,
                        miningNode: miningNode, respawnSeconds: seconds);
                }
                return new SpawnInfo(SpawnState.Alive, liveNPC: npc, miningNode: miningNode);
            }

            return new SpawnInfo(SpawnState.Alive, liveNPC: npc);
        }

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
                return new SpawnInfo(SpawnState.Alive, sp, sp.SpawnedNPC);

            return new SpawnInfo(SpawnState.NightLocked, sp);
        }

        // Alive with expected NPC
        if (IsExpectedNPCAlive(sp, expectedNPCName))
            return new SpawnInfo(SpawnState.Alive, sp, sp.SpawnedNPC);

        // Alive but wrong NPC (rare/common mismatch) — treat as not found
        // for this particular quest target. Also handles stale MyNPCAlive
        // where the reference was lost (SpawnedNPC null after zone reload).
        if (sp.MyNPCAlive && sp.SpawnedNPC != null)
            return new SpawnInfo(SpawnState.NotFound, sp);

        // Dead, respawning
        float tickRate = 60f * GetSpawnTimeMod();
        float seconds2 = tickRate > 0f ? sp.actualSpawnDelay / tickRate : 0f;
        return new SpawnInfo(SpawnState.Dead, sp, respawnSeconds: seconds2);
    }

    /// <summary>Night spawn window: hour > 22 OR hour &lt; 4.</summary>
    private static bool IsNightHours()
    {
        int hour = GameData.Time.GetHour();
        return hour > 22 || hour < 4;
    }

    /// <summary>Maximum squared distance for matching directly-placed NPCs.</summary>
    /// <remarks>Observed drift is under 0.25m; 2m threshold is generous.</remarks>
    private const float MaxDriftSqr = 4f;

    /// <summary>
    /// Find a live NPC matching the expected name within proximity of the
    /// static spawn position. Uses the name cache built during Rebuild.
    /// Destroyed NPCs (Unity-null) are skipped.
    /// </summary>
    private NPC? FindDirectlyPlacedNPC(float x, float y, float z, string expectedName)
    {
        if (!_npcByName.TryGetValue(expectedName.ToLowerInvariant(), out var candidates))
            return null;

        var target = new Vector3(x, y, z);
        foreach (var npc in candidates)
        {
            // Unity fake-null: destroyed since Rebuild
            if (npc == null) continue;
            if ((npc.transform.position - target).sqrMagnitude <= MaxDriftSqr)
                return npc;
        }
        return null;
    }

    private static float GetSpawnTimeMod()
    {
        var gm = GameData.GM;
        return gm != null ? gm.SpawnTimeMod : 1f;
    }

    // ── Mining node helpers ─────────────────────────────────────────
    // Canonical mining state logic lives in MiningNodeTracker.

    public static bool IsMiningNodeMined(MiningNode node) =>
        MiningNodeTracker.IsMined(node);

    public static float GetMiningNodeRespawnSeconds(MiningNode node) =>
        MiningNodeTracker.GetRemainingSeconds(node) ?? 0f;
}
