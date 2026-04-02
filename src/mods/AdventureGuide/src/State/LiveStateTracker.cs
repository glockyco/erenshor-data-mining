using System.Reflection;
using AdventureGuide.Graph;
using UnityEngine;

namespace AdventureGuide.State;

/// <summary>
/// Tracks live spawn, character, mining, item-bag, and time-of-day state.
/// Emits precise live-world fact deltas so downstream maintained views can
/// invalidate only derivations that depend on changed sources.
/// </summary>
public sealed class LiveStateTracker
{
    private static readonly FieldInfo? NpcSpawnPointField =
        typeof(NPC).GetField("MySpawnPoint", BindingFlags.Instance | BindingFlags.NonPublic);

    private static readonly FieldInfo? MiningRespawnField =
        typeof(MiningNode).GetField("Respawn", BindingFlags.Instance | BindingFlags.NonPublic);

    private readonly EntityGraph _graph;
    private readonly GraphIndexes _indexes;
    private readonly EntityRegistry _entities;
    private readonly GuideDependencyEngine _dependencies;
    private readonly UnlockEvaluator _unlocks;

    private Dictionary<PosKey, SpawnPoint> _spawnIndex = new();
    private readonly Dictionary<string, List<NPC>> _npcByName = new(System.StringComparer.OrdinalIgnoreCase);
    private MiningNode[] _miningNodes = System.Array.Empty<MiningNode>();
    private ItemBag[] _itemBags = System.Array.Empty<ItemBag>();
    private Door[] _doors = System.Array.Empty<Door>();
    private readonly Dictionary<PosKey, bool> _miningAvailable = new();
    private readonly Dictionary<PosKey, bool> _doorClosed = new();

    private readonly Dictionary<PosKey, string> _graphSpawnSourcesByPos = new();
    private readonly Dictionary<PosKey, string> _graphMiningSourcesByPos = new();
    private readonly Dictionary<PosKey, string> _graphItemBagSourcesByPos = new();
    private readonly Dictionary<PosKey, string> _graphDoorSourcesByPos = new();
    private readonly Dictionary<string, List<Node>> _directSpawnNodesByNpcName = new(System.StringComparer.OrdinalIgnoreCase);

    public int Version { get; private set; }
    private bool _isNight;

    public LiveStateTracker(
        EntityGraph graph,
        GraphIndexes indexes,
        EntityRegistry entities,
        GuideDependencyEngine dependencies,
        UnlockEvaluator unlocks)
    {
        _graph = graph;
        _indexes = indexes;
        _entities = entities;
        _dependencies = dependencies;
        _unlocks = unlocks;
    }

    public void OnSceneLoaded()
    {
        RebuildSpawnIndex();
        RebuildNpcNameCache();
        RebuildGraphSourceIndexes();
        _miningNodes = UnityEngine.Object.FindObjectsOfType<MiningNode>();
        _itemBags = UnityEngine.Object.FindObjectsOfType<ItemBag>();
        _doors = UnityEngine.Object.FindObjectsOfType<Door>();
        _isNight = IsNight();
        RebuildMiningAvailability();
        RebuildDoorStates();
        BumpVersion();
    }

    public GuideChangeSet OnNPCSpawn(SpawnPoint sp)
    {
        if (sp == null)
            return GuideChangeSet.None;

        BumpVersion();
        var sourceKey = ResolveSpawnSourceKey(sp);
        return BuildSourceChange(sourceKey);
    }

    public GuideChangeSet OnNPCDeath(NPC npc)
    {
        if (npc == null)
            return GuideChangeSet.None;

        BumpVersion();

        var sourceKey = ResolveNpcSourceKey(npc);
        return BuildSourceChange(sourceKey);
    }

    public GuideChangeSet OnMiningChanged(MiningNode mn)
    {
        if (mn == null)
            return GuideChangeSet.None;

        _miningAvailable[NodePosKey(mn.transform.position)] = IsMiningNodeAvailable(mn);
        BumpVersion();
        return BuildSourceChange(ResolveMiningSourceKey(mn));
    }

    public GuideChangeSet OnItemBagChanged(ItemBag bag)
    {
        if (bag == null)
            return GuideChangeSet.None;

        BumpVersion();
        return BuildSourceChange(ResolveItemBagSourceKey(bag));
    }

    public GuideChangeSet UpdateFrameState()
    {
        bool changed = false;
        bool timeChanged = false;
        var changedSourceKeys = new HashSet<string>(StringComparer.Ordinal);

        bool nowNight = IsNight();
        if (nowNight != _isNight)
        {
            _isNight = nowNight;
            changed = true;
            timeChanged = true;
        }

        foreach (var mn in _miningNodes)
        {
            if (mn == null)
                continue;

            var key = NodePosKey(mn.transform.position);
            bool available = IsMiningNodeAvailable(mn);
            if (_miningAvailable.TryGetValue(key, out var previous) && previous == available)
                continue;

            _miningAvailable[key] = available;
            changed = true;

            var sourceKey = ResolveMiningSourceKey(mn);
            if (!string.IsNullOrEmpty(sourceKey))
                changedSourceKeys.Add(sourceKey);
        }

        foreach (var door in _doors)
        {
            if (door == null)
                continue;

            var key = NodePosKey(door.transform.position);
            bool isClosed = door.isClosed && !door.swinging;
            if (_doorClosed.TryGetValue(key, out var previous) && previous == isClosed)
                continue;

            _doorClosed[key] = isClosed;
            changed = true;

            var sourceKey = ResolveDoorSourceKey(door);
            if (!string.IsNullOrEmpty(sourceKey))
                changedSourceKeys.Add(sourceKey);
        }

        if (!changed)
            return GuideChangeSet.None;

        BumpVersion();
        return BuildLiveChange(changedSourceKeys, timeChanged);
    }

    public SpawnInfo GetSpawnState(Node spawnNode)
    {
        if (spawnNode == null)
            return new SpawnInfo(NodeState.Unknown, null, null, 0f);

        _dependencies.RecordFact(new GuideFactKey(GuideFactKind.SourceState, spawnNode.Key));

        if (!LiveSceneScope.CanUseLiveSceneState(spawnNode.Scene, CurrentSceneName()))
            return new SpawnInfo(NodeState.Unknown, null, null, 0f);

        if (spawnNode.IsDirectlyPlaced)
            return ResolveDirectlyPlacedSpawn(spawnNode);

        var sp = FindSpawnPoint(spawnNode);
        if (sp != null)
            return ClassifySpawnPoint(sp);

        var npc = FindNpcByNameAndProximity(GetSpawnOwnerCharacter(spawnNode) ?? spawnNode);
        if (npc != null)
        {
            var ch = npc.GetComponent<Character>();
            bool alive = ch != null && ch.Alive;
            return new SpawnInfo(alive ? NodeState.Alive : new SpawnDead(0f), null, npc, 0f);
        }

        return new SpawnInfo(NodeState.Unknown, null, null, 0f);
    }

    public SpawnInfo GetCharacterState(Node characterNode)
    {
        if (characterNode == null)
            return new SpawnInfo(NodeState.Unknown, null, null, 0f);

        _dependencies.RecordFact(new GuideFactKey(GuideFactKind.SourceState, characterNode.Key));

        string? unlockReason = GetCharacterUnlockRequirement(characterNode);
        if (!LiveSceneScope.CharacterHasCurrentScenePresence(_graph, characterNode, CurrentSceneName()))
        {
            return string.IsNullOrEmpty(unlockReason)
                ? new SpawnInfo(NodeState.Unknown, null, null, 0f)
                : new SpawnInfo(new SpawnUnlockBlocked(unlockReason), null, null, 0f);
        }

        if (!string.IsNullOrEmpty(unlockReason))
            return new SpawnInfo(new SpawnUnlockBlocked(unlockReason), null, null, 0f);

        var spawnEdges = _graph.OutEdges(characterNode.Key, EdgeType.HasSpawn);
        SpawnInfo best = new SpawnInfo(NodeState.Unknown, null, null, 0f);
        bool found = false;

        for (int i = 0; i < spawnEdges.Count; i++)
        {
            var spawnNode = _graph.GetNode(spawnEdges[i].Target);
            if (spawnNode == null)
                continue;

            var info = GetSpawnState(spawnNode);
            if (!found || IsBetterState(info.State, best.State))
            {
                best = info;
                found = true;
            }
        }

        if (found && best.State is not UnknownState)
            return best;

        var npc = FindNpcByNameAndProximity(characterNode);
        if (npc != null)
        {
            var ch = npc.GetComponent<Character>();
            bool alive = ch != null && ch.Alive;
            return new SpawnInfo(alive ? NodeState.Alive : new SpawnDead(0f), null, npc, 0f);
        }

        return new SpawnInfo(NodeState.Unknown, null, null, 0f);
    }

    public MiningInfo GetMiningState(Node miningNode)
    {
        if (miningNode == null)
            return new MiningInfo(NodeState.Unknown, null);

        _dependencies.RecordFact(new GuideFactKey(GuideFactKind.SourceState, miningNode.Key));

        if (!LiveSceneScope.CanUseLiveSceneState(miningNode.Scene, CurrentSceneName()))
            return new MiningInfo(NodeState.Unknown, null);

        var posKey = NodePosKey(miningNode);
        if (!posKey.HasValue)
            return new MiningInfo(NodeState.Unknown, null);

        MiningNode? closest = null;
        float closestDist = float.MaxValue;

        foreach (var mn in _miningNodes)
        {
            if (mn == null)
                continue;

            float dist = Vector3.Distance(
                mn.transform.position,
                new Vector3(miningNode.X ?? 0f, miningNode.Y ?? 0f, miningNode.Z ?? 0f));
            if (dist < closestDist)
            {
                closestDist = dist;
                closest = mn;
            }
        }

        if (closest == null || closestDist > 2f)
            return new MiningInfo(NodeState.Unknown, null);

        return ClassifyMiningNode(closest);
    }

    public NodeState GetItemBagState(Node itemBagNode)
    {
        if (itemBagNode == null)
            return NodeState.Unknown;

        _dependencies.RecordFact(new GuideFactKey(GuideFactKind.SourceState, itemBagNode.Key));

        if (!LiveSceneScope.CanUseLiveSceneState(itemBagNode.Scene, CurrentSceneName()))
            return NodeState.Unknown;

        var posKey = NodePosKey(itemBagNode);
        if (!posKey.HasValue)
            return NodeState.Unknown;

        ItemBag? closest = null;
        float closestDist = float.MaxValue;
        foreach (var bag in _itemBags)
        {
            if (bag == null)
                continue;

            float dist = Vector3.Distance(
                bag.transform.position,
                new Vector3(itemBagNode.X ?? 0f, itemBagNode.Y ?? 0f, itemBagNode.Z ?? 0f));
            if (dist < closestDist)
            {
                closestDist = dist;
                closest = bag;
            }
        }

        if (closest != null && closestDist <= 2f)
            return NodeState.BagAvailable;

        // Bag is missing from the scene. The game recreates all ItemBags on
        // scene reload; the only permanent removal is in Start() for unique
        // items the player already owns. The Respawns field is unused by the
        // game. Treat every missing bag as picked up (re-enter zone to respawn).
        return new ItemBagPickedUp(0f);
    }

    public DoorInfo GetDoorState(Node doorNode)
    {
        if (doorNode == null)
            return new DoorInfo(NodeState.Unknown, null, false);

        _dependencies.RecordFact(new GuideFactKey(GuideFactKind.SourceState, doorNode.Key));

        if (!LiveSceneScope.CanUseLiveSceneState(doorNode.Scene, CurrentSceneName()))
            return new DoorInfo(NodeState.Unknown, null, false);

        var posKey = NodePosKey(doorNode);
        if (!posKey.HasValue)
            return new DoorInfo(NodeState.Unknown, null, false);

        Door? closest = null;
        float closestDist = float.MaxValue;
        foreach (var door in _doors)
        {
            if (door == null)
                continue;

            float dist = Vector3.Distance(
                door.transform.position,
                new Vector3(doorNode.X ?? 0f, doorNode.Y ?? 0f, doorNode.Z ?? 0f));
            if (dist < closestDist)
            {
                closestDist = dist;
                closest = door;
            }
        }

        if (closest == null || closestDist > 2f)
            return new DoorInfo(NodeState.Unknown, null, false);

        return !closest.isClosed || closest.swinging
            ? new DoorInfo(NodeState.Unlocked, closest, true)
            : new DoorInfo(NodeState.Unknown, closest, true);
    }

    private SpawnInfo ClassifySpawnPoint(SpawnPoint sp)
    {
        if (!sp.canSpawn)
        {
            if (sp.SpawnUponQuestComplete != null
                && !GameData.IsQuestDone(sp.SpawnUponQuestComplete.DBName))
            {
                string questName = sp.SpawnUponQuestComplete.QuestName
                    ?? sp.SpawnUponQuestComplete.DBName
                    ?? "unknown quest";
                return new SpawnInfo(new SpawnUnlockBlocked($"Requires: {questName}"), sp, null, 0f);
            }

            return new SpawnInfo(NodeState.Disabled, sp, null, 0f);
        }

        if (sp.NightSpawn)
        {
            _dependencies.RecordFact(new GuideFactKey(GuideFactKind.TimeOfDay, "night"));
            if (!IsNight())
                return new SpawnInfo(NodeState.NightLocked, sp, null, 0f);
        }

        if (IsSpawnedNPCAlive(sp))
            return new SpawnInfo(NodeState.Alive, sp, sp.SpawnedNPC, 0f);

        float respawnSeconds = ComputeRespawnSeconds(sp);
        return new SpawnInfo(new SpawnDead(respawnSeconds), sp, sp.SpawnedNPC, respawnSeconds);
    }

    private MiningInfo ClassifyMiningNode(MiningNode mn)
    {
        var render = mn.MyRender;
        if (render != null && !render.enabled)
        {
            float respawnSeconds = GetMiningRespawnSeconds(mn);
            return new MiningInfo(new MiningMined(respawnSeconds), mn);
        }

        return new MiningInfo(NodeState.MineAvailable, mn);
    }

    private void RebuildSpawnIndex()
    {
        _spawnIndex.Clear();
        var spawnPoints = SpawnPointManager.SpawnPointsInScene;
        if (spawnPoints == null)
            return;

        foreach (var sp in spawnPoints)
        {
            if (sp == null)
                continue;

            var key = new PosKey(sp.transform.position.x, sp.transform.position.y, sp.transform.position.z);
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
            if (npc == null || string.IsNullOrEmpty(npc.NPCName))
                continue;

            string nameLower = npc.NPCName.ToLowerInvariant();
            if (!_npcByName.TryGetValue(nameLower, out var list))
            {
                list = new List<NPC>(2);
                _npcByName[nameLower] = list;
            }

            list.Add(npc);
        }
    }

    private void RebuildGraphSourceIndexes()
    {
        _graphSpawnSourcesByPos.Clear();
        _graphMiningSourcesByPos.Clear();
        _graphItemBagSourcesByPos.Clear();
        _graphDoorSourcesByPos.Clear();
        _directSpawnNodesByNpcName.Clear();

        string currentScene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
        foreach (var node in _graph.AllNodes)
        {
            if (!string.Equals(node.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;

            var posKey = NodePosKey(node);
            switch (node.Type)
            {
                case NodeType.SpawnPoint when posKey.HasValue:
                    if (!_graphSpawnSourcesByPos.ContainsKey(posKey.Value))
                        _graphSpawnSourcesByPos[posKey.Value] = node.Key;
                    if (node.IsDirectlyPlaced)
                        AddDirectSpawnNode(node);
                    break;
                case NodeType.MiningNode when posKey.HasValue:
                    if (!_graphMiningSourcesByPos.ContainsKey(posKey.Value))
                        _graphMiningSourcesByPos[posKey.Value] = node.Key;
                    break;
                case NodeType.ItemBag when posKey.HasValue:
                    if (!_graphItemBagSourcesByPos.ContainsKey(posKey.Value))
                        _graphItemBagSourcesByPos[posKey.Value] = node.Key;
                    break;
                case NodeType.Door when posKey.HasValue:
                    if (!_graphDoorSourcesByPos.ContainsKey(posKey.Value))
                        _graphDoorSourcesByPos[posKey.Value] = node.Key;
                    break;
            }
        }
    }

    private void AddDirectSpawnNode(Node spawnNode)
    {
        string name = LiveSceneScope.ResolveSpawnLookupName(
            spawnNode,
            GetSpawnOwnerCharacter(spawnNode));
        if (string.IsNullOrEmpty(name))
            return;

        string key = name.ToLowerInvariant();
        if (!_directSpawnNodesByNpcName.TryGetValue(key, out var list))
        {
            list = new List<Node>(1);
            _directSpawnNodesByNpcName[key] = list;
        }

        list.Add(spawnNode);
    }

    private SpawnInfo ResolveDirectlyPlacedSpawn(Node spawnNode)
    {
        var charNode = GetSpawnOwnerCharacter(spawnNode);
        if (charNode != null)
        {
            string? unlockReason = GetCharacterUnlockRequirement(charNode);
            if (!string.IsNullOrEmpty(unlockReason))
                return new SpawnInfo(new SpawnUnlockBlocked(unlockReason), null, null, 0f);

            var npc = FindNpcByNameAndProximity(charNode);
            if (npc != null)
            {
                var ch = npc.GetComponent<Character>();
                bool alive = ch != null && ch.Alive;
                return new SpawnInfo(alive ? NodeState.Alive : new SpawnDead(0f), null, npc, 0f);
            }

            return new SpawnInfo(new SpawnDead(0f), null, null, 0f);
        }

        var fallbackNpc = FindNpcByNameAndProximity(spawnNode);
        if (fallbackNpc != null)
        {
            var ch = fallbackNpc.GetComponent<Character>();
            bool alive = ch != null && ch.Alive;
            return new SpawnInfo(alive ? NodeState.Alive : new SpawnDead(0f), null, fallbackNpc, 0f);
        }

        return new SpawnInfo(NodeState.Unknown, null, null, 0f);
    }

    private string? GetCharacterUnlockRequirement(Node charNode)
    {
        var evaluation = _unlocks.Evaluate(charNode);
        return evaluation.IsUnlocked ? null : evaluation.Reason;
    }

    private string CurrentSceneName() => UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;

    private Node? GetSpawnOwnerCharacter(Node spawnNode)
    {
        var charEdges = _graph.InEdges(spawnNode.Key, EdgeType.HasSpawn);
        if (charEdges.Count == 0)
            return null;

        return _graph.GetNode(charEdges[0].Source);
    }


    private SpawnPoint? FindSpawnPoint(Node node)
    {
        var posKey = NodePosKey(node);
        return posKey.HasValue && _spawnIndex.TryGetValue(posKey.Value, out var sp) ? sp : null;
    }

    private NPC? FindNpcByNameAndProximity(Node node)
    {
        if (string.IsNullOrEmpty(node.DisplayName))
            return null;

        string nameLower = node.DisplayName.ToLowerInvariant();
        if (!_npcByName.TryGetValue(nameLower, out var candidates))
            return null;

        if (!node.X.HasValue || !node.Y.HasValue || !node.Z.HasValue)
        {
            foreach (var npc in candidates)
            {
                if (npc == null)
                    continue;

                var ch = npc.GetComponent<Character>();
                if (ch != null && ch.Alive)
                    return npc;
            }

            return null;
        }

        var nodePos = new Vector3(node.X.Value, node.Y.Value, node.Z.Value);
        NPC? best = null;
        float bestDist = float.MaxValue;

        foreach (var npc in candidates)
        {
            if (npc == null)
                continue;

            float dist = Vector3.Distance(npc.transform.position, nodePos);
            if (dist < bestDist)
            {
                bestDist = dist;
                best = npc;
            }
        }

        return best;
    }

    private string? ResolveSpawnSourceKey(SpawnPoint sp)
    {
        var key = NodePosKey(sp.transform.position);
        return _graphSpawnSourcesByPos.TryGetValue(key, out var sourceKey) ? sourceKey : null;
    }

    private string? ResolveMiningSourceKey(MiningNode miningNode)
    {
        var key = NodePosKey(miningNode.transform.position);
        return _graphMiningSourcesByPos.TryGetValue(key, out var sourceKey) ? sourceKey : null;
    }

    private string? ResolveItemBagSourceKey(ItemBag bag)
    {
        var key = NodePosKey(bag.transform.position);
        return _graphItemBagSourcesByPos.TryGetValue(key, out var sourceKey) ? sourceKey : null;
    }

    private string? ResolveDoorSourceKey(Door door)
    {
        var key = NodePosKey(door.transform.position);
        return _graphDoorSourcesByPos.TryGetValue(key, out var sourceKey) ? sourceKey : null;
    }

    private string? ResolveNpcSourceKey(NPC npc)
    {
        if (NpcSpawnPointField?.GetValue(npc) is SpawnPoint spawnPoint)
            return ResolveSpawnSourceKey(spawnPoint);

        if (!string.IsNullOrEmpty(npc.NPCName)
            && _directSpawnNodesByNpcName.TryGetValue(npc.NPCName.ToLowerInvariant(), out var candidates)
            && candidates.Count > 0)
        {
            Node? best = null;
            float bestDist = float.MaxValue;
            for (int i = 0; i < candidates.Count; i++)
            {
                var candidate = candidates[i];
                if (!candidate.X.HasValue || !candidate.Y.HasValue || !candidate.Z.HasValue)
                    continue;

                float dist = Vector3.Distance(
                    npc.transform.position,
                    new Vector3(candidate.X.Value, candidate.Y.Value, candidate.Z.Value));
                if (dist < bestDist)
                {
                    bestDist = dist;
                    best = candidate;
                }
            }

            if (best != null)
                return best.Key;
        }

        return null;
    }

    private GuideChangeSet BuildSourceChange(string? sourceKey)
    {
        if (string.IsNullOrEmpty(sourceKey))
            return GuideChangeSet.None;

        return BuildLiveChange(new[] { sourceKey }, timeChanged: false);
    }

    private GuideChangeSet BuildLiveChange(IEnumerable<string> changedSourceKeys, bool timeChanged)
    {
        var sourceKeys = new HashSet<string>(changedSourceKeys.Where(k => !string.IsNullOrWhiteSpace(k)), StringComparer.Ordinal);
        var changedFacts = new List<GuideFactKey>();
        foreach (var sourceKey in sourceKeys)
            changedFacts.Add(new GuideFactKey(GuideFactKind.SourceState, sourceKey));
        if (timeChanged)
            changedFacts.Add(new GuideFactKey(GuideFactKind.TimeOfDay, "night"));

        if (changedFacts.Count == 0)
            return GuideChangeSet.None;

        var affectedQuestKeys = new HashSet<string>(StringComparer.Ordinal);
        foreach (var sourceKey in sourceKeys)
        {
            foreach (var questKey in _indexes.GetQuestsTouchingSource(sourceKey))
                affectedQuestKeys.Add(questKey);
        }

        return new GuideChangeSet(
            inventoryChanged: false,
            questLogChanged: false,
            sceneChanged: false,
            liveWorldChanged: true,
            changedItemKeys: Array.Empty<string>(),
            changedQuestDbNames: Array.Empty<string>(),
            affectedQuestKeys: affectedQuestKeys,
            changedFacts: changedFacts);
    }

    private void RebuildMiningAvailability()
    {
        _miningAvailable.Clear();
        foreach (var mn in _miningNodes)
        {
            if (mn == null)
                continue;

            _miningAvailable[NodePosKey(mn.transform.position)] = IsMiningNodeAvailable(mn);
        }
    }

    private void RebuildDoorStates()
    {
        _doorClosed.Clear();
        foreach (var door in _doors)
        {
            if (door == null)
                continue;

            _doorClosed[NodePosKey(door.transform.position)] = door.isClosed && !door.swinging;
        }
    }

    private void BumpVersion() => Version++;

    private static bool IsNight()
    {
        // GameData.Time may be null during early scene load before the game
        // manager has initialized. Treat as daytime rather than throwing.
        if (GameData.Time == null) return false;
        int hour = GameData.Time.GetHour();
        return hour >= 22 || hour < 4;
    }

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
        if (spawnTimeMod <= 0f)
            spawnTimeMod = 1f;
        return sp.actualSpawnDelay / (60f * spawnTimeMod);
    }

    private static float GetMiningRespawnSeconds(MiningNode mn)
    {
        if (MiningRespawnField == null)
            return 0f;

        object? val = MiningRespawnField.GetValue(mn);
        return val is float ticks ? ticks / 60f : 0f;
    }

    private static bool IsBetterState(NodeState candidate, NodeState current) =>
        GetStatePriority(candidate) > GetStatePriority(current);

    private static int GetStatePriority(NodeState state)
    {
        if (state is SpawnAlive) return 3;
        if (state is SpawnDead) return 2;
        if (state is SpawnNightLocked) return 1;
        return 0;
    }

    private static bool IsMiningNodeAvailable(MiningNode mn) =>
        mn.MyRender != null && mn.MyRender.enabled;

    private static PosKey? NodePosKey(Node node)
    {
        if (!node.X.HasValue || !node.Y.HasValue || !node.Z.HasValue)
            return null;
        return new PosKey(node.X.Value, node.Y.Value, node.Z.Value);
    }

    private static PosKey NodePosKey(Vector3 pos) => new PosKey(pos.x, pos.y, pos.z);

    private readonly struct PosKey : System.IEquatable<PosKey>
    {
        private readonly int _x;
        private readonly int _y;
        private readonly int _z;

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

public readonly struct DoorInfo
{
    public readonly NodeState State;
    public readonly Door? LiveDoor;
    public readonly bool FoundInScene;

    public DoorInfo(NodeState state, Door? liveDoor, bool foundInScene)
    {
        State = state;
        LiveDoor = liveDoor;
        FoundInScene = foundInScene;
    }
}
