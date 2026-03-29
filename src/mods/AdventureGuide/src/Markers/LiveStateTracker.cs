using System.Reflection;
using AdventureGuide.Graph;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.Markers;

/// <summary>
/// Tracks live spawn, character, and mining node state by correlating graph nodes
/// with in-scene game objects. Rebuilt on scene load; updated incrementally via
/// Harmony patch callbacks (spawn/death).
/// </summary>
public sealed class LiveStateTracker
{
    // ── Reflection cache ────────────────────────────────────────────────

    private static readonly FieldInfo? NpcSpawnPointField =
        typeof(NPC).GetField("MySpawnPoint", BindingFlags.Instance | BindingFlags.NonPublic);

    private static readonly FieldInfo? MiningRespawnField =
        typeof(MiningNode).GetField("Respawn", BindingFlags.Instance | BindingFlags.NonPublic);

    // ── Dependencies ────────────────────────────────────────────────────

    private readonly EntityGraph _graph;
    private readonly EntityRegistry _entities;

    // ── Scene-local caches (rebuilt on scene load) ──────────────────────

    private Dictionary<PosKey, SpawnPoint> _spawnIndex = new();
    private Dictionary<string, List<NPC>> _npcByName = new(System.StringComparer.OrdinalIgnoreCase);
    private MiningNode[] _miningNodes = System.Array.Empty<MiningNode>();

    // ── Dirty flag ──────────────────────────────────────────────────────

    public bool IsDirty { get; private set; }

    public void ClearDirty() => IsDirty = false;

    // ── Constructor ─────────────────────────────────────────────────────

    public LiveStateTracker(EntityGraph graph, EntityRegistry entities)
    {
        _graph = graph;
        _entities = entities;
    }

    // ── Scene load ──────────────────────────────────────────────────────

    /// <summary>
    /// Rebuild all scene-local caches. Call on every scene transition.
    /// </summary>
    public void OnSceneLoaded()
    {
        RebuildSpawnIndex();
        RebuildNpcNameCache();
        _miningNodes = UnityEngine.Object.FindObjectsOfType<MiningNode>();
        IsDirty = true;
    }

    // ── Patch callbacks ─────────────────────────────────────────────────

    public void OnNPCSpawn(SpawnPoint sp)
    {
        if (sp == null) return;
        IsDirty = true;
    }

    public void OnNPCDeath(NPC npc)
    {
        if (npc == null) return;
        IsDirty = true;
    }

    // ── Public state queries ────────────────────────────────────────────

    public SpawnInfo GetSpawnState(Node spawnNode)
    {
        if (spawnNode == null)
            return new SpawnInfo(NodeState.Unknown, null, null, 0f);

        // Directly-placed NPCs have no runtime SpawnPoint — find by character name.
        if (spawnNode.IsDirectlyPlaced)
            return ResolveDirectlyPlacedSpawn(spawnNode);

        var sp = FindSpawnPoint(spawnNode);
        if (sp != null)
            return ClassifySpawnPoint(sp);

        // Fallback: try to find a directly-placed NPC by name + proximity.
        var npc = FindNpcByNameAndProximity(spawnNode);
        if (npc != null)
        {
            var ch = npc.GetComponent<Character>();
            bool alive = ch != null && ch.Alive;
            return new SpawnInfo(
                alive ? NodeState.Alive : new SpawnDead(0f),
                null,
                npc,
                0f);
        }

        return new SpawnInfo(NodeState.Unknown, null, null, 0f);
    }

    public SpawnInfo GetCharacterState(Node characterNode)
    {
        if (characterNode == null)
            return new SpawnInfo(NodeState.Unknown, null, null, 0f);

        // Characters connect to spawn points via HAS_SPAWN edges (character → spawn_point).
        var spawnEdges = _graph.OutEdges(characterNode.Key, EdgeType.HasSpawn);

        SpawnInfo best = new SpawnInfo(NodeState.Unknown, null, null, 0f);
        bool found = false;

        for (int i = 0; i < spawnEdges.Count; i++)
        {
            var spawnNode = _graph.GetNode(spawnEdges[i].Target);
            if (spawnNode == null) continue;

            var info = GetSpawnState(spawnNode);
            if (!found || IsBetterState(info.State, best.State))
            {
                best = info;
                found = true;
            }
        }

        if (found && best.State is not UnknownState)
            return best;

        // Spawn edges returned Unknown or no edges at all — try name-based lookup.
        var npc = FindNpcByNameAndProximity(characterNode);
        if (npc != null)
        {
            var ch = npc.GetComponent<Character>();
            bool alive = ch != null && ch.Alive;
            return new SpawnInfo(
                alive ? NodeState.Alive : new SpawnDead(0f),
                null,
                npc,
                0f);
        }

        return new SpawnInfo(NodeState.Unknown, null, null, 0f);
    }

    public MiningInfo GetMiningState(Node miningNode)
    {
        if (miningNode == null)
            return new MiningInfo(NodeState.Unknown, null);

        // Find the live MiningNode by position match.
        var posKey = NodePosKey(miningNode);
        if (!posKey.HasValue)
            return new MiningInfo(NodeState.Unknown, null);

        MiningNode? closest = null;
        float closestDist = float.MaxValue;

        foreach (var mn in _miningNodes)
        {
            if (mn == null) continue;
            var pos = mn.transform.position;
            float dist = Vector3.Distance(
                pos,
                new Vector3(miningNode.X ?? 0f, miningNode.Y ?? 0f, miningNode.Z ?? 0f));
            if (dist < closestDist)
            {
                closestDist = dist;
                closest = mn;
            }
        }

        // Allow up to 2m tolerance for position matching.
        if (closest == null || closestDist > 2f)
            return new MiningInfo(NodeState.Unknown, null);

        return ClassifyMiningNode(closest);
    }

    // ── Spawn point classification ──────────────────────────────────────

    private SpawnInfo ClassifySpawnPoint(SpawnPoint sp)
    {
        // canSpawn=false has three causes in the game:
        //   1. SpawnUponQuestComplete set, quest not done → gated, will appear later
        //   2. StopIfQuestComplete quest done → permanently gone
        //   3. Scripted event (ReliqDisableFiendSpawn, FernallaFightEvent) → unknown
        // Only case 1 produces a useful marker. Cases 2 and 3 return Disabled
        // so MarkerComputer skips them (no marker is better than a wrong one).
        if (!sp.canSpawn)
        {
            if (sp.SpawnUponQuestComplete != null
                && !GameData.IsQuestDone(sp.SpawnUponQuestComplete.DBName))
            {
                string questName = sp.SpawnUponQuestComplete.QuestName
                    ?? sp.SpawnUponQuestComplete.DBName
                    ?? "unknown quest";
                return new SpawnInfo(new SpawnQuestGated(questName), sp, null, 0f);
            }
            return new SpawnInfo(NodeState.Disabled, sp, null, 0f);
        }

        // Night-locked: NightSpawn is true but it's currently daytime.
        if (sp.NightSpawn && !IsNight())
            return new SpawnInfo(NodeState.NightLocked, sp, null, 0f);

        // Alive: NPC is up and its Character component is alive.
        // sp.MyNPCAlive is unreliable — it's set true on spawn but never
        // cleared on death. The game itself checks SpawnedNPC.GetChar().Alive.
        if (IsSpawnedNPCAlive(sp))
            return new SpawnInfo(NodeState.Alive, sp, sp.SpawnedNPC, 0f);

        // Dead: NPC has been killed, compute respawn timer.
        float respawnSeconds = ComputeRespawnSeconds(sp);
        return new SpawnInfo(new SpawnDead(respawnSeconds), sp, null, respawnSeconds);
    }

    private MiningInfo ClassifyMiningNode(MiningNode mn)
    {
        // Mined = renderer disabled.
        var render = mn.MyRender;
        if (render != null && !render.enabled)
        {
            float respawnSeconds = GetMiningRespawnSeconds(mn);
            return new MiningInfo(new MiningMined(respawnSeconds), mn);
        }

        return new MiningInfo(NodeState.MineAvailable, mn);
    }

    // ── Index builders ──────────────────────────────────────────────────

    private void RebuildSpawnIndex()
    {
        _spawnIndex.Clear();
        var spawnPoints = SpawnPointManager.SpawnPointsInScene;
        if (spawnPoints == null) return;

        foreach (var sp in spawnPoints)
        {
            if (sp == null) continue;
            var pos = sp.transform.position;
            var key = new PosKey(pos.x, pos.y, pos.z);
            // First one wins — duplicates at exact position are unlikely.
            if (!_spawnIndex.ContainsKey(key))
                _spawnIndex[key] = sp;
        }
    }

    private void RebuildNpcNameCache()
    {
        _npcByName.Clear();
        var npcs = UnityEngine.Object.FindObjectsOfType<NPC>();
        foreach (var npc in npcs)
        {
            if (npc == null || string.IsNullOrEmpty(npc.NPCName)) continue;
            string nameLower = npc.NPCName.ToLowerInvariant();
            if (!_npcByName.TryGetValue(nameLower, out var list))
            {
                list = new List<NPC>(2);
                _npcByName[nameLower] = list;
            }
            list.Add(npc);
        }
    }

    // ── Lookups ─────────────────────────────────────────────────────────

    /// <summary>
    /// Resolve a directly-placed spawn node by finding the live NPC via
    /// its character name. Directly-placed NPCs have no runtime SpawnPoint
    /// component — they exist as scene objects and are always present.
    /// </summary>
    private SpawnInfo ResolveDirectlyPlacedSpawn(Node spawnNode)
    {
        // Find the character this spawn point belongs to via HasSpawn edge
        var charEdges = _graph.InEdges(spawnNode.Key, EdgeType.HasSpawn);
        if (charEdges.Count > 0)
        {
            var charNode = _graph.GetNode(charEdges[0].Source);
            if (charNode != null)
            {
                var npc = FindNpcByNameAndProximity(charNode);
                if (npc != null)
                {
                    var ch = npc.GetComponent<Character>();
                    bool alive = ch != null && ch.Alive;
                    return new SpawnInfo(
                        alive ? NodeState.Alive : new SpawnDead(0f),
                        null, npc, 0f);
                }
            }
        }

        // Last resort: try by spawn node's own display name
        var fallbackNpc = FindNpcByNameAndProximity(spawnNode);
        if (fallbackNpc != null)
        {
            var ch = fallbackNpc.GetComponent<Character>();
            bool alive = ch != null && ch.Alive;
            return new SpawnInfo(
                alive ? NodeState.Alive : new SpawnDead(0f),
                null, fallbackNpc, 0f);
        }

        return new SpawnInfo(NodeState.Unknown, null, null, 0f);
    }

    private SpawnPoint? FindSpawnPoint(Node node)
    {
        var posKey = NodePosKey(node);
        if (posKey.HasValue && _spawnIndex.TryGetValue(posKey.Value, out var sp))
            return sp;
        return null;
    }

    private NPC? FindNpcByNameAndProximity(Node node)
    {
        if (string.IsNullOrEmpty(node.DisplayName)) return null;
        string nameLower = node.DisplayName.ToLowerInvariant();

        if (!_npcByName.TryGetValue(nameLower, out var candidates))
            return null;

        if (!node.X.HasValue || !node.Y.HasValue || !node.Z.HasValue)
        {
            // No position data — return first alive candidate.
            foreach (var npc in candidates)
            {
                if (npc == null) continue;
                var ch = npc.GetComponent<Character>();
                if (ch != null && ch.Alive) return npc;
            }
            return null;
        }

        var nodePos = new Vector3(node.X.Value, node.Y.Value, node.Z.Value);
        NPC? best = null;
        float bestDist = float.MaxValue;

        foreach (var npc in candidates)
        {
            if (npc == null) continue;
            float dist = Vector3.Distance(npc.transform.position, nodePos);
            if (dist < bestDist)
            {
                bestDist = dist;
                best = npc;
            }
        }

        return best;
    }

    // ── Helpers ──────────────────────────────────────────────────────────

    private static bool IsNight()
    {
        int hour = GameData.Time.GetHour();
        return hour >= 22 || hour < 4;
    }

    /// <summary>
    /// Check whether a SpawnPoint's NPC is alive. Matches the game's own
    /// check in SpawnPoint.Update: SpawnedNPC != null and GetChar().Alive.
    /// Do NOT use sp.MyNPCAlive — it is set on spawn but never cleared on death.
    /// </summary>
    private static bool IsSpawnedNPCAlive(SpawnPoint sp)
    {
        return sp.SpawnedNPC != null
            && sp.SpawnedNPC.gameObject != null
            && sp.SpawnedNPC.GetChar() != null
            && sp.SpawnedNPC.GetChar().Alive;
    }

    private static float ComputeRespawnSeconds(SpawnPoint sp)
    {
        float spawnTimeMod = GameData.GM.SpawnTimeMod;
        if (spawnTimeMod <= 0f) spawnTimeMod = 1f;
        return sp.actualSpawnDelay / (60f * spawnTimeMod);
    }

    private static float GetMiningRespawnSeconds(MiningNode mn)
    {
        if (MiningRespawnField == null) return 0f;
        object? val = MiningRespawnField.GetValue(mn);
        if (val is float ticks)
            return ticks / 60f;
        return 0f;
    }

    /// <summary>
    /// Returns true if <paramref name="candidate"/> is a "better" (more favorable)
    /// state than <paramref name="current"/>. Alive > Dead > everything else.
    /// </summary>
    private static bool IsBetterState(NodeState candidate, NodeState current)
    {
        return GetStatePriority(candidate) > GetStatePriority(current);
    }

    private static int GetStatePriority(NodeState state)
    {
        if (state is SpawnAlive) return 3;
        if (state is SpawnDead) return 2;
        if (state is SpawnNightLocked) return 1;
        return 0;
    }

    private static PosKey? NodePosKey(Node node)
    {
        if (!node.X.HasValue || !node.Y.HasValue || !node.Z.HasValue)
            return null;
        return new PosKey(node.X.Value, node.Y.Value, node.Z.Value);
    }

    private static PosKey NodePosKey(Vector3 pos) => new PosKey(pos.x, pos.y, pos.z);

    // ── PosKey ──────────────────────────────────────────────────────────

    /// <summary>
    /// Position key with centimeter precision for O(1) spawn point lookup.
    /// </summary>
    private readonly struct PosKey : System.IEquatable<PosKey>
    {
        private readonly int _x, _y, _z;

        public PosKey(float x, float y, float z)
        {
            _x = (int)(x * 100f);
            _y = (int)(y * 100f);
            _z = (int)(z * 100f);
        }

        public bool Equals(PosKey other) => _x == other._x && _y == other._y && _z == other._z;
        public override bool Equals(object? obj) => obj is PosKey other && Equals(other);
        public override int GetHashCode() => (_x * 397) ^ (_y * 17) ^ _z;
    }
}

// ── Result structs ──────────────────────────────────────────────────────

/// <summary>Live state snapshot for a spawn point or character node.</summary>
public readonly struct SpawnInfo
{
    public readonly NodeState State;
    public readonly SpawnPoint? LiveSpawnPoint;
    public readonly NPC? LiveNPC;
    public readonly float RespawnSeconds;

    public SpawnInfo(NodeState state, SpawnPoint? liveSpawnPoint, NPC? liveNPC, float respawnSeconds)
    {
        State = state;
        LiveSpawnPoint = liveSpawnPoint;
        LiveNPC = liveNPC;
        RespawnSeconds = respawnSeconds;
    }
}

/// <summary>Live state snapshot for a mining node.</summary>
public readonly struct MiningInfo
{
    public readonly NodeState State;
    public readonly MiningNode? LiveNode;

    public MiningInfo(NodeState state, MiningNode? liveNode)
    {
        State = state;
        LiveNode = liveNode;
    }
}
