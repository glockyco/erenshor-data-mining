using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Bridges static spawn data (from quest-guide.json) to live game SpawnPoint
/// objects. Each scene index maps SpawnPoints by rounded position for O(1)
/// lookup and records which points the player left respawning the last time
/// they left the scene. Directly-placed NPCs (no SpawnPoint) are matched by
/// name and proximity against an NPC cache built with the index. Destroyed
/// NPCs are filtered out at lookup time through Unity's fake-null.
/// </summary>
public sealed class SpawnPointBridge
{
    /// <summary>State of a spawn for marker decisions.</summary>
    public enum SpawnState
    {
        /// <summary>The NPC the marker targets is alive.</summary>
        Alive,

        /// <summary>A different NPC from the spawn table is alive at the SpawnPoint.</summary>
        OtherAlive,

        /// <summary>The NPC died or despawned, and its respawn timer runs.</summary>
        Dead,

        /// <summary>Mining node has been mined and is regenerating.</summary>
        Mined,

        /// <summary>Night-only spawn during daytime hours.</summary>
        NightLocked,

        /// <summary>The zone load is populating the SpawnPoint; its NPC appears within seconds.</summary>
        Populating,

        /// <summary>
        /// The SpawnPoint cannot spawn: a quest gate, an encounter script, or a
        /// completed stop quest holds it.
        /// </summary>
        Withheld,

        /// <summary>Directly-placed NPC that died — respawns on zone re-entry.</summary>
        DirectlyPlacedDead,
    }

    /// <summary>Result of a spawn lookup with live state.</summary>
    public readonly struct SpawnInfo
    {
        public readonly SpawnState State;
        public readonly SpawnPoint? LiveSpawnPoint;
        public readonly NPC? LiveNPC;
        public readonly MiningNode? LiveMiningNode;
        public readonly float RespawnSeconds;

        public SpawnInfo(
            SpawnState state,
            SpawnPoint? liveSP = null,
            NPC? liveNPC = null,
            MiningNode? miningNode = null,
            float respawnSeconds = 0f
        )
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
        private readonly int _x,
            _y,
            _z;

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
    private readonly List<SpawnPoint> _spawnPoints = new();
    private int _indexedRegistrations = -1;

    // SpawnPoint IDs the game saved with a running respawn timer when the
    // player last left their scene.
    private readonly HashSet<string> _restoredRespawns = new(System.StringComparer.Ordinal);

    // SpawnPoint instance ID → name of the NPC it spawned most recently in
    // this scene visit. Filled by the SpawnNPC postfix.
    private readonly Dictionary<int, string> _lastSpawnedNames = new();

    // SpawnPoint instance ID → the only NPC name its spawn table holds, or
    // null when the table names several NPCs.
    private readonly Dictionary<int, string?> _spawnTableNames = new();

    // Directly-placed NPC cache: name (lowercase) → list of NPC references.
    // Built once per Rebuild from FindObjectsOfType. Destroyed NPCs become
    // Unity-null between rebuilds, filtered at lookup time.
    private readonly Dictionary<string, List<NPC>> _npcByName = new();

    /// <summary>Live SpawnPoints of the indexed scene.</summary>
    public IReadOnlyList<SpawnPoint> SpawnPoints => _spawnPoints;

    /// <summary>
    /// True when SpawnPoints registered with SpawnPointManager since the last
    /// index. Registration happens in SpawnPoint.Start, which also restores
    /// the point's saved respawn timer; encounter areas that switch on later
    /// register their points only then. SceneChange clears the list before the
    /// next scene loads, so a shrinking list is not a change.
    /// </summary>
    public bool HasNewRegistrations =>
        (SpawnPointManager.SpawnPointsInScene?.Count ?? 0) > _indexedRegistrations;

    /// <summary>
    /// Forget the previous scene. Call from the scene-load callback, before the
    /// new scene spawns its first NPC.
    /// </summary>
    public void OnSceneLoaded()
    {
        _index.Clear();
        _spawnPoints.Clear();
        _restoredRespawns.Clear();
        _lastSpawnedNames.Clear();
        _spawnTableNames.Clear();
        _npcByName.Clear();
        _indexedRegistrations = 0;
    }

    /// <summary>Remember which NPC a SpawnPoint produced. Call from the SpawnNPC postfix.</summary>
    public void RecordSpawn(SpawnPoint spawnPoint)
    {
        var npc = spawnPoint.SpawnedNPC;
        if (npc != null && !string.IsNullOrWhiteSpace(npc.NPCName))
            _lastSpawnedNames[spawnPoint.GetInstanceID()] = npc.NPCName.Trim();
    }

    /// <summary>
    /// Rebuild the index and the directly-placed NPC cache from the current
    /// scene. Call on scene change, before marker rebuild.
    /// </summary>
    public void Rebuild()
    {
        _index.Clear();
        _spawnPoints.Clear();
        _spawnTableNames.Clear();

        // A SpawnPoint registers with SpawnPointManager only in its Start.
        // Index the active components directly, so the index holds every point
        // whether or not Start has run yet; before Start a point reads as
        // still populating, and is never mistaken for a directly-placed NPC.
        foreach (var sp in UnityEngine.Object.FindObjectsOfType<SpawnPoint>())
            AddToIndex(sp);
        _indexedRegistrations = 0;
        IndexNewRegistrations();

        // SceneChange saves every SpawnPoint's timer when the player leaves a
        // scene, and SpawnPoint.Start restores a positive one on return. A
        // positive saved timer means the NPC was dead or despawned then.
        _restoredRespawns.Clear();
        var saved = SpawnPointManager.AllSavePoints;
        if (saved != null)
        {
            foreach (var entry in saved)
            {
                if (entry != null && entry.RespawnTimer > 0f && entry.Identifier != null)
                    _restoredRespawns.Add(entry.Identifier);
            }
        }

        _npcByName.Clear();
        // Cache all active NPCs by lowercase name for directly-placed lookup.
        // One FindObjectsOfType call per scene load, reused for all GetState calls.
        foreach (var npc in UnityEngine.Object.FindObjectsOfType<NPC>())
        {
            if (npc == null || string.IsNullOrEmpty(npc.NPCName))
                continue;
            var nameKey = npc.NPCName.ToLowerInvariant();
            if (!_npcByName.TryGetValue(nameKey, out var list))
            {
                list = new List<NPC>();
                _npcByName[nameKey] = list;
            }
            list.Add(npc);
        }
    }

    /// <summary>Index SpawnPoints that registered since the last call.</summary>
    public void IndexNewRegistrations()
    {
        var registered = SpawnPointManager.SpawnPointsInScene;
        if (registered == null)
        {
            _indexedRegistrations = 0;
            return;
        }
        // SceneChange clears the list; start over when it shrank.
        if (registered.Count < _indexedRegistrations)
            _indexedRegistrations = 0;
        for (int i = _indexedRegistrations; i < registered.Count; i++)
            AddToIndex(registered[i]);
        _indexedRegistrations = registered.Count;
    }

    private void AddToIndex(SpawnPoint sp)
    {
        if (sp == null)
            return;
        var pos = sp.transform.position;
        // First SpawnPoint at a position wins (collisions not expected)
        if (_index.TryAdd(new PosKey(pos.x, pos.y, pos.z), sp))
            _spawnPoints.Add(sp);
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
                    return new SpawnInfo(
                        SpawnState.Mined,
                        liveNPC: npc,
                        miningNode: miningNode,
                        respawnSeconds: seconds
                    );
                }
                return new SpawnInfo(SpawnState.Alive, liveNPC: npc, miningNode: miningNode);
            }

            return new SpawnInfo(SpawnState.Alive, liveNPC: npc);
        }

        return new SpawnInfo(SpawnState.DirectlyPlacedDead);
    }

    /// <summary>
    /// Respawn phase of a live SpawnPoint. A null target name accepts any
    /// living NPC from the spawn table.
    /// </summary>
    internal SpawnPointPhase GetPhase(SpawnPoint sp, string? targetName)
    {
        bool anyAlive = sp.MyNPCAlive && sp.SpawnedNPC != null;
        bool targetAlive = anyAlive && (targetName == null || IsTargetAlive(sp, targetName));
        var facts = new SpawnPointFacts(
            anyAlive,
            targetAlive,
            sp.canSpawn,
            IsStopQuestCompleted(sp),
            sp.NightSpawn,
            GameData.Time.GetHour(),
            HasRespawnHistory(sp)
        );
        return SpawnPointPolicy.Classify(facts);
    }

    /// <summary>
    /// True once the SpawnPoint spawned during this visit, or when the player
    /// left it respawning on their previous visit. Until then, an empty point
    /// is still being populated by the zone load.
    /// </summary>
    public bool HasRespawnHistory(SpawnPoint sp) =>
        sp.SpawnIteration > 0
        || (!sp.SpawnPointIgnoresPastData && sp.ID != null && _restoredRespawns.Contains(sp.ID));

    /// <summary>
    /// Name for a respawn marker without a quest target: the NPC the point
    /// last spawned this visit, else the only name its spawn table holds,
    /// else null.
    /// </summary>
    public string? GetRespawnLabel(SpawnPoint sp)
    {
        int id = sp.GetInstanceID();
        if (_lastSpawnedNames.TryGetValue(id, out var last))
            return last;
        if (!_spawnTableNames.TryGetValue(id, out var tableName))
        {
            tableName = FindOnlySpawnName(sp);
            _spawnTableNames[id] = tableName;
        }
        return tableName;
    }

    /// <summary>
    /// Check if a specific NPC name is alive at a SpawnPoint, accounting for
    /// rare/common spawn variants. Returns true when the spawned NPC's name
    /// matches the expected quest target.
    /// </summary>
    public static bool IsTargetAlive(SpawnPoint sp, string expectedName)
    {
        return sp.MyNPCAlive
            && sp.SpawnedNPC != null
            && string.Equals(
                sp.SpawnedNPC.NPCName,
                expectedName,
                System.StringComparison.OrdinalIgnoreCase
            );
    }

    /// <summary>
    /// Real seconds until the SpawnPoint may spawn again. SpawnPoint.Update
    /// subtracts 60 × SpawnTimeMod ticks per second while it can spawn.
    /// </summary>
    public static float GetRespawnSeconds(SpawnPoint sp)
    {
        float tickRate = 60f * (GameData.GM != null ? GameData.GM.SpawnTimeMod : 1f);
        return tickRate > 0f ? sp.actualSpawnDelay / tickRate : 0f;
    }

    private SpawnInfo ClassifySpawnPoint(SpawnPoint sp, string expectedNPCName)
    {
        return GetPhase(sp, expectedNPCName) switch
        {
            SpawnPointPhase.TargetAlive => new SpawnInfo(SpawnState.Alive, sp, sp.SpawnedNPC),
            SpawnPointPhase.OtherAlive => new SpawnInfo(SpawnState.OtherAlive, sp),
            SpawnPointPhase.Withheld => new SpawnInfo(SpawnState.Withheld, sp),
            SpawnPointPhase.NightLocked => new SpawnInfo(SpawnState.NightLocked, sp),
            SpawnPointPhase.Populating => new SpawnInfo(SpawnState.Populating, sp),
            _ => new SpawnInfo(SpawnState.Dead, sp, respawnSeconds: GetRespawnSeconds(sp)),
        };
    }

    /// <summary>
    /// SpawnPoint.Update stops a point for good once any of its
    /// StopIfQuestComplete quests is completed and its timer runs out.
    /// </summary>
    private static bool IsStopQuestCompleted(SpawnPoint sp)
    {
        var quests = sp.StopIfQuestComplete;
        if (quests == null || quests.Count == 0 || GameData.CompletedQuests == null)
            return false;
        foreach (var quest in quests)
        {
            if (quest != null && GameData.CompletedQuests.Contains(quest.DBName))
                return true;
        }
        return false;
    }

    private static string? FindOnlySpawnName(SpawnPoint sp)
    {
        string? only = null;
        if (!CollectOnlySpawnName(sp.CommonSpawns, ref only))
            return null;
        if (!CollectOnlySpawnName(sp.RareSpawns, ref only))
            return null;
        return only;
    }

    /// <summary>Returns false as soon as a second distinct NPC name appears.</summary>
    private static bool CollectOnlySpawnName(List<GameObject>? spawns, ref string? only)
    {
        if (spawns == null)
            return true;
        foreach (var prefab in spawns)
        {
            if (prefab == null)
                continue;
            var npc = prefab.GetComponent<NPC>();
            if (npc == null || string.IsNullOrWhiteSpace(npc.NPCName))
                continue;
            var name = npc.NPCName.Trim();
            if (only == null)
                only = name;
            else if (!string.Equals(only, name, System.StringComparison.OrdinalIgnoreCase))
                return false;
        }
        return true;
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
            if (npc == null)
                continue;
            if ((npc.transform.position - target).sqrMagnitude <= MaxDriftSqr)
                return npc;
        }
        return null;
    }

    // ── Mining node helpers ─────────────────────────────────────────
    // Canonical mining state logic lives in MiningNodeTracker.

    public static bool IsMiningNodeMined(MiningNode node) => MiningNodeTracker.IsMined(node);

    public static float GetMiningNodeRespawnSeconds(MiningNode node) =>
        MiningNodeTracker.GetRemainingSeconds(node) ?? 0f;
}
