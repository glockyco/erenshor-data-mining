using System.Reflection;
using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Markers;
using UnityEngine;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.State;

/// <summary>
/// Tracks live spawn, character, mining, item-bag, and time-of-day state.
/// Emits precise live-world fact deltas so downstream maintained views can
/// invalidate only derivations that depend on changed sources.
/// </summary>
public sealed class LiveStateTracker
    : IResolutionLiveState,
        INavigationSelectorLiveState,
        IMarkerLiveStateProvider,
        ISourceStateFactSource
{
    private static readonly FieldInfo? NpcSpawnPointField = typeof(NPC).GetField(
        "MySpawnPoint",
        BindingFlags.Instance | BindingFlags.NonPublic
    );

    private static readonly FieldInfo? MiningRespawnField = typeof(MiningNode).GetField(
        "Respawn",
        BindingFlags.Instance | BindingFlags.NonPublic
    );

    private readonly CompiledGuideModel _guide;
    private readonly UnlockEvaluator _unlocks;

    private Dictionary<PosKey, SpawnPoint> _spawnIndex = new();
    private readonly Dictionary<string, List<NPC>> _npcByName = new(
        System.StringComparer.OrdinalIgnoreCase
    );
    private MiningNode[] _miningNodes = System.Array.Empty<MiningNode>();
    private ItemBag[] _itemBags = System.Array.Empty<ItemBag>();
    private Door[] _doors = System.Array.Empty<Door>();
    private readonly List<RotChest> _rotChests = new();
    private readonly Dictionary<PosKey, bool> _miningAvailable = new();
    private readonly Dictionary<PosKey, bool> _itemBagAvailable = new();
    private readonly Dictionary<PosKey, bool> _doorClosed = new();

    private readonly Dictionary<PosKey, string> _graphSpawnSourcesByPos = new();
    private readonly Dictionary<PosKey, string> _graphMiningSourcesByPos = new();
    private readonly Dictionary<PosKey, string> _graphItemBagSourcesByPos = new();
    private readonly Dictionary<PosKey, string> _graphDoorSourcesByPos = new();
    private readonly Dictionary<string, List<Node>> _directSpawnNodesByNpcName = new(
        System.StringComparer.OrdinalIgnoreCase
    );

    private bool _isNight;

    public LiveStateTracker(
        CompiledGuideModel guide,
        UnlockEvaluator unlocks
    )
    {
        _guide = guide;
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
        _rotChests.Clear();
        _isNight = IsNight();
        RebuildMiningAvailability();
        RebuildItemBagAvailability();
        RebuildDoorStates();
        
    }

    public ChangeSet OnNPCSpawn(SpawnPoint sp)
    {
        if (sp == null)
            return ChangeSet.None;

        
        var sourceKey = ResolveSpawnSourceKey(sp);
        return BuildSourceChange(sourceKey);
    }

    public ChangeSet OnNPCDeath(NPC npc)
    {
        if (npc == null)
            return ChangeSet.None;

        var sourceKey = ResolveNpcSourceKey(npc);
        return BuildSourceChange(sourceKey);
    }

    public ChangeSet OnCorpseLooted(NPC npc)
    {
        if (npc == null)
            return ChangeSet.None;

        var sourceKey = ResolveNpcSourceKey(npc);
        return BuildSourceChange(sourceKey);
    }

    public ChangeSet OnMiningChanged(MiningNode mn)
    {
        if (mn == null)
            return ChangeSet.None;

        _miningAvailable[NodePosKey(mn.transform.position)] = IsMiningNodeAvailable(mn);
        
        return BuildSourceChange(ResolveMiningSourceKey(mn));
    }

    public ChangeSet OnItemBagChanged(ItemBag bag)
    {
        if (bag == null)
            return ChangeSet.None;

        _itemBagAvailable[NodePosKey(bag.transform.position)] = false;
        
        return BuildSourceChange(ResolveItemBagSourceKey(bag));
    }

    /// <summary>
    /// Called after CorpseDataManager.SpawnAllCorpses to register all RotChest
    /// objects created from saved corpse data. Returns a liveWorldChanged changeset
    /// so the resolution service rebuilds targets that may include chest loot.
    /// </summary>
    public ChangeSet OnAllCorpsesSpawned()
    {
        _rotChests.Clear();
        var chests = UnityEngine.Object.FindObjectsOfType<RotChest>();
        foreach (var chest in chests)
        {
            if (chest != null)
                _rotChests.Add(chest);
        }

        if (_rotChests.Count == 0)
            return ChangeSet.None;

        // Mark all quests in the current scene as potentially affected — any active
        // quest that needs an item from a DropsItem source could now find the item
        // in a loot chest.
        
        return BuildLiveChange(_graphSpawnSourcesByPos.Values, timeChanged: false);
    }

    /// <summary>
    /// Returns the world position and scene name for every RotChest in the current
    /// scene whose loot table contains the specified item. Called live on each
    /// query; no additional caching is applied so chest contents stay fresh after
    /// partial looting.
    /// </summary>
    public System.Collections.Generic.IEnumerable<LiveChestPosition> GetRotChestPositionsWithItem(
        string itemStableKey
    )
    {
        string currentScene = CurrentSceneName();
        for (int i = _rotChests.Count - 1; i >= 0; i--)
        {
            var chest = _rotChests[i];
            if (chest == null || chest.gameObject == null)
            {
                _rotChests.RemoveAt(i);
                continue;
            }

            var loot = chest.GetComponent<LootTable>();
            if (loot == null)
                continue;

            foreach (var drop in loot.ActualDrops)
            {
                if (drop != null && "item:" + drop.name.Trim().ToLowerInvariant() == itemStableKey)
                {
                    var pos = chest.transform.position;
                    yield return new LiveChestPosition(pos.x, pos.y, pos.z, currentScene);
                    break;
                }
            }
        }
    }

    /// <summary>
    /// Returns the first RotChest within <paramref name="maxDistance"/> of
    /// <paramref name="position"/>, or null if none is found. Used by
    /// MarkerProjector to bind a live chest reference to a marker entry.
    /// </summary>
    public RotChest? GetRotChestNear(Vector3 position, float maxDistance = 1f)
    {
        for (int i = 0; i < _rotChests.Count; i++)
        {
            var chest = _rotChests[i];
            if (chest == null || chest.gameObject == null)
                continue;
            if (Vector3.Distance(chest.transform.position, position) <= maxDistance)
                return chest;
        }
        return null;
    }

    public ChangeSet UpdateFrameState()
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
            return ChangeSet.None;

        
        // forceChanged: a state change was detected above; emit the signal even
        // when no specific source key could be resolved from the changed nodes.
        return BuildLiveChange(changedSourceKeys, timeChanged, forceChanged: true);
    }

    public SpawnInfo GetSpawnState(Node spawnNode)
    {
        if (spawnNode == null)
            return new SpawnInfo(NodeState.Unknown, null, null, 0f);

        RecordLiveStateDeps(spawnNode);

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

        RecordLiveStateDeps(characterNode);

        string? unlockReason = GetCharacterUnlockRequirement(characterNode);
        if (
            !LiveSceneScope.CharacterHasCurrentScenePresence(
                _guide,
                characterNode,
                CurrentSceneName()
            )
        )
        {
            return string.IsNullOrEmpty(unlockReason)
                ? new SpawnInfo(NodeState.Unknown, null, null, 0f)
                : new SpawnInfo(new SpawnUnlockBlocked(unlockReason), null, null, 0f);
        }

        if (!string.IsNullOrEmpty(unlockReason))
            return new SpawnInfo(new SpawnUnlockBlocked(unlockReason), null, null, 0f);

        var spawnEdges = _guide.OutEdges(characterNode.Key, EdgeType.HasSpawn);
        SpawnInfo best = new SpawnInfo(NodeState.Unknown, null, null, 0f);
        bool found = false;

        for (int i = 0; i < spawnEdges.Count; i++)
        {
            var spawnNode = _guide.GetNode(spawnEdges[i].Target);
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

        RecordLiveStateDeps(miningNode);

        if (!LiveSceneScope.CanUseLiveSceneState(miningNode.Scene, CurrentSceneName()))
            return new MiningInfo(NodeState.Unknown, null);

        var posKey = NodePosKey(miningNode);
        if (!posKey.HasValue)
            return new MiningInfo(NodeState.Unknown, null);

        var targetPos = new Vector3(miningNode.X ?? 0f, miningNode.Y ?? 0f, miningNode.Z ?? 0f);
        var best = FindBestPositionMatch(
            posKey.Value,
            targetPos,
            _miningNodes,
            mn => mn.transform.position
        );
        if (best == null)
            return new MiningInfo(NodeState.Unknown, null);

        return ClassifyMiningNode(best);
    }

    public NodeState GetItemBagState(Node itemBagNode)
    {
        if (itemBagNode == null)
            return NodeState.Unknown;

        RecordLiveStateDeps(itemBagNode);

        if (!LiveSceneScope.CanUseLiveSceneState(itemBagNode.Scene, CurrentSceneName()))
            return NodeState.Unknown;

        if (TryGetCachedItemBagAvailability(itemBagNode, out bool available))
            return available ? NodeState.BagAvailable : new ItemBagPickedUp(0f);

        var posKey = NodePosKey(itemBagNode);
        if (!posKey.HasValue)
            return NodeState.Unknown;

        var targetPos = new Vector3(itemBagNode.X ?? 0f, itemBagNode.Y ?? 0f, itemBagNode.Z ?? 0f);
        var best = FindBestPositionMatch(
            posKey.Value,
            targetPos,
            _itemBags,
            bag => bag.transform.position
        );
        if (best != null)
            return NodeState.BagAvailable;

        return new ItemBagPickedUp(0f);
    }

    public DoorInfo GetDoorState(Node doorNode)
    {
        if (doorNode == null)
            return new DoorInfo(NodeState.Unknown, null, false);

        RecordLiveStateDeps(doorNode);

        if (!LiveSceneScope.CanUseLiveSceneState(doorNode.Scene, CurrentSceneName()))
            return new DoorInfo(NodeState.Unknown, null, false);

        if (TryGetCachedDoorClosed(doorNode, out bool isClosed))
        {
            return !isClosed
                ? new DoorInfo(NodeState.Unlocked, null, true)
                : new DoorInfo(NodeState.Unknown, null, true);
        }

        var posKey = NodePosKey(doorNode);
        if (!posKey.HasValue)
            return new DoorInfo(NodeState.Unknown, null, false);

        var targetPos = new Vector3(doorNode.X ?? 0f, doorNode.Y ?? 0f, doorNode.Z ?? 0f);
        var best = FindBestPositionMatch(
            posKey.Value,
            targetPos,
            _doors,
            door => door.transform.position
        );
        if (best == null)
            return new DoorInfo(NodeState.Unknown, null, false);

        return !best.isClosed || best.swinging
            ? new DoorInfo(NodeState.Unlocked, best, true)
            : new DoorInfo(NodeState.Unknown, best, true);
    }

    public bool TryGetCachedMiningAvailability(Node miningNode, out bool available) =>
        TryGetCachedPositionFlag(miningNode, _miningAvailable, out available);

    public bool TryGetCachedItemBagAvailability(Node itemBagNode, out bool available) =>
        TryGetCachedPositionFlag(itemBagNode, _itemBagAvailable, out available);

    public bool TryGetCachedDoorClosed(Node doorNode, out bool isClosed) =>
        TryGetCachedPositionFlag(doorNode, _doorClosed, out isClosed);

    /// <summary>
    /// Returns true when the spawn node's corpse is present in the scene and its
    /// loot table contains the required item. Works for both spawn-point and
    /// directly-placed NPCs — GetSpawnState resolves info.LiveNPC regardless of
    /// NPC type, and the loot check is purely on the corpse game object.
    /// </summary>
    public bool CorpseContainsItem(Node spawnNode, string itemStableKey)
    {
        var info = GetSpawnState(spawnNode);
        if (!(info.State is SpawnDead))
            return false;
        if (info.LiveNPC == null || info.LiveNPC.gameObject == null)
            return false;

        var loot = info.LiveNPC.GetComponent<LootTable>();
        if (loot == null)
            return false;

        foreach (var drop in loot.ActualDrops)
        {
            if (drop != null && "item:" + drop.name.Trim().ToLowerInvariant() == itemStableKey)
                return true;
        }
        return false;
    }

    /// <summary>
    /// Returns the alive NPC currently occupying <paramref name="spawnNode"/> for
    /// per-frame position tracking. Does NOT record dependency facts — use only
    /// from NavigationEngine.Track(), not from resolution passes.
    ///
    /// For spawn-point NPCs: reads SpawnPoint.SpawnedNPC (a direct inspector
    /// reference set by SpawnPoint.SpawnNPC) — zero string key lookup.
    /// For directly-placed NPCs (IsDirectlyPlaced): scans NPCTable.LiveNPCs
    /// by NPCName, which is the in-game display name, not an export pipeline key.
    /// </summary>
    public NPC? GetLiveNpcForTracking(Node spawnNode)
    {
        if (!spawnNode.IsDirectlyPlaced)
        {
            var posKey = NodePosKey(spawnNode);
            if (!posKey.HasValue)
                return null;
            if (!_spawnIndex.TryGetValue(posKey.Value, out var sp))
                return null;

            if (sp.SpawnedNPC == null || !sp.SpawnedNPC.gameObject)
                return null;
            var ch = sp.SpawnedNPC.GetComponent<Character>();
            if (ch == null || !ch.Alive)
                return null;
            return sp.SpawnedNPC;
        }
        else
        {
            if (NPCTable.LiveNPCs == null)
                return null;
            for (int i = 0; i < NPCTable.LiveNPCs.Count; i++)
            {
                var npc = NPCTable.LiveNPCs[i];
                if (npc == null || npc.gameObject == null)
                    continue;
                if (npc.NPCName.Equals(spawnNode.DisplayName, StringComparison.OrdinalIgnoreCase))
                    return npc;
            }
            return null;
        }
    }

    /// <summary>
    /// Returns the live world position of the NPC at the given spawn node, or null
    /// if the NPC is not alive or not in scene. Returns a value tuple so callers
    /// that cannot reference Assembly-CSharp (e.g. NavigationTargetSelector in tests)
    /// are not forced to load game types at JIT time.
    /// </summary>
    public (float x, float y, float z)? GetLiveNpcPosition(Node spawnNode)
    {
        RecordLiveStateDeps(spawnNode);
        var npc = GetLiveNpcForTracking(spawnNode);
        if (npc == null)
            return null;
        var pos = npc.transform.position;
        return (pos.x, pos.y, pos.z);
    }

    /// <summary>
    /// Returns true when the spawn point has no live game object at all — either
    /// the NPC has not yet spawned or the corpse has fully rotted away. Returns
    /// false when a game object exists (alive NPC or present corpse), when the
    /// spawn node is directly-placed (those respawn on zone reentry, not via
    /// SpawnPoint), or when the spawn is not found in the scene index.
    ///
    /// Used by NavigationTargetSelector to distinguish "corpse present" (do not
    /// touch isActionable) from "spawn empty" (reset to static coords, non-actionable).
    /// </summary>
    public bool IsSpawnEmpty(Node spawnNode)
    {
        if (spawnNode.IsDirectlyPlaced)
            return false;
        var posKey = NodePosKey(spawnNode);
        if (!posKey.HasValue)
            return false;
        if (!_spawnIndex.TryGetValue(posKey.Value, out var sp))
            return false;
        // Empty = SpawnedNPC never set, or the game object has been destroyed
        return sp.SpawnedNPC == null || !sp.SpawnedNPC.gameObject;
    }

    private SpawnInfo ClassifySpawnPoint(SpawnPoint sp)
    {
        if (!sp.canSpawn)
        {
            if (
                sp.SpawnUponQuestComplete != null
                && !GameData.IsQuestDone(sp.SpawnUponQuestComplete.DBName)
            )
            {
                string questName =
                    sp.SpawnUponQuestComplete.QuestName
                    ?? sp.SpawnUponQuestComplete.DBName
                    ?? "unknown quest";
                return new SpawnInfo(
                    new SpawnUnlockBlocked($"Requires: {questName}"),
                    sp,
                    null,
                    0f
                );
            }

            return new SpawnInfo(NodeState.Disabled, sp, null, 0f);
        }

        if (sp.NightSpawn)
        {

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

            var key = new PosKey(
                sp.transform.position.x,
                sp.transform.position.y,
                sp.transform.position.z
            );
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
        foreach (var node in _guide.AllNodes)
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
            GetSpawnOwnerCharacter(spawnNode)
        );
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
            return new SpawnInfo(
                alive ? NodeState.Alive : new SpawnDead(0f),
                null,
                fallbackNpc,
                0f
            );
        }

        return new SpawnInfo(NodeState.Unknown, null, null, 0f);
    }

    private string? GetCharacterUnlockRequirement(Node charNode)
    {
        var evaluation = _unlocks.Evaluate(charNode);
        return evaluation.IsUnlocked ? null : evaluation.Reason;
    }

    private string CurrentSceneName() =>
        UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;

    private Node? GetSpawnOwnerCharacter(Node spawnNode)
    {
        var charEdges = _guide.InEdges(spawnNode.Key, EdgeType.HasSpawn);
        if (charEdges.Count == 0)
            return null;

        return _guide.GetNode(charEdges[0].Source);
    }

    private SpawnPoint? FindSpawnPoint(Node node)
    {
        var posKey = NodePosKey(node);
        return posKey.HasValue && _spawnIndex.TryGetValue(posKey.Value, out var sp) ? sp : null;
    }

    private static T? FindBestPositionMatch<T>(
        PosKey targetKey,
        Vector3 targetPosition,
        IReadOnlyList<T> candidates,
        System.Func<T, Vector3> positionSelector,
        float maxDistance = 2f
    )
        where T : class
    {
        for (int i = 0; i < candidates.Count; i++)
        {
            var candidate = candidates[i];
            if (candidate == null)
                continue;

            if (NodePosKey(positionSelector(candidate)).Equals(targetKey))
                return candidate;
        }

        T? best = null;
        float bestDist = maxDistance;
        for (int i = 0; i < candidates.Count; i++)
        {
            var candidate = candidates[i];
            if (candidate == null)
                continue;

            float dist = Vector3.Distance(positionSelector(candidate), targetPosition);
            if (dist < bestDist)
            {
                bestDist = dist;
                best = candidate;
            }
        }

        return best;
    }

    internal static int FindBestPositionMatchIndex(
        (float X, float Y, float Z) targetPosition,
        IReadOnlyList<(float X, float Y, float Z)> candidatePositions,
        float maxDistance = 2f
    )
    {
        var targetKey = new PosKey(targetPosition.X, targetPosition.Y, targetPosition.Z);
        for (int i = 0; i < candidatePositions.Count; i++)
        {
            var candidate = candidatePositions[i];
            if (new PosKey(candidate.X, candidate.Y, candidate.Z).Equals(targetKey))
                return i;
        }

        int bestIndex = -1;
        float bestDistSquared = maxDistance * maxDistance;
        for (int i = 0; i < candidatePositions.Count; i++)
        {
            var candidate = candidatePositions[i];
            float dx = candidate.X - targetPosition.X;
            float dy = candidate.Y - targetPosition.Y;
            float dz = candidate.Z - targetPosition.Z;
            float distSquared = dx * dx + dy * dy + dz * dz;
            if (distSquared < bestDistSquared)
            {
                bestDistSquared = distSquared;
                bestIndex = i;
            }
        }

        return bestIndex;
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

        if (
            !string.IsNullOrEmpty(npc.NPCName)
            && _directSpawnNodesByNpcName.TryGetValue(
                npc.NPCName.ToLowerInvariant(),
                out var candidates
            )
            && candidates.Count > 0
        )
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
                    new Vector3(candidate.X.Value, candidate.Y.Value, candidate.Z.Value)
                );
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

    private ChangeSet BuildSourceChange(string? sourceKey)
    {
        // Always emit a meaningful changeset so the downstream system rebuilds.
        // When the source key is unknown (position not in graph), emit a generic
        // liveWorldChanged signal; selective invalidation falls back to wholesale.
        return string.IsNullOrEmpty(sourceKey)
            ? BuildLiveChange(Array.Empty<string>(), timeChanged: false, forceChanged: true)
            : BuildLiveChange(new[] { sourceKey }, timeChanged: false);
    }

    private ChangeSet BuildLiveChange(
        IEnumerable<string> changedSourceKeys,
        bool timeChanged,
        // forceChanged: emit a liveWorldChanged changeset even when no specific
        // source facts are available (e.g. a node whose position is not in the
        // graph index). Without this the caller would silently return None and the
        // NAV system would never learn the world changed.
        bool forceChanged = false
    )
    {
        var sourceKeys = new HashSet<string>(
            changedSourceKeys.Where(k => !string.IsNullOrWhiteSpace(k)),
            StringComparer.Ordinal
        );
        var changedFacts = new List<FactKey>();
        foreach (var sourceKey in sourceKeys)
            changedFacts.Add(new FactKey(FactKind.SourceState, sourceKey));
        if (sourceKeys.Count > 0)
            changedFacts.Add(new FactKey(FactKind.SourceState, "*"));
        if (timeChanged)
            changedFacts.Add(new FactKey(FactKind.TimeOfDay, "current"));

        if (!forceChanged && changedFacts.Count == 0)
            return ChangeSet.None;

        var affectedQuestKeys = new HashSet<string>(StringComparer.Ordinal);
        foreach (var sourceKey in sourceKeys)
        {
            foreach (var questKey in _guide.GetQuestsTouchingSource(sourceKey))
                affectedQuestKeys.Add(questKey);
        }

        return new ChangeSet(
            inventoryChanged: false,
            questLogChanged: false,
            sceneChanged: false,
            liveWorldChanged: true,
            changedItemKeys: Array.Empty<string>(),
            changedQuestDbNames: Array.Empty<string>(),
            affectedQuestKeys: affectedQuestKeys,
            changedFacts: changedFacts
        );
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

    private void RebuildItemBagAvailability()
    {
        _itemBagAvailable.Clear();
        foreach (var bag in _itemBags)
        {
            if (bag == null)
                continue;

            _itemBagAvailable[NodePosKey(bag.transform.position)] = true;
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

    private static bool IsNight()
    {
        // GameData.Time may be null during early scene load before the game
        // manager has initialized. Treat as daytime rather than throwing.
        if (GameData.Time == null)
            return false;
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
        if (state is SpawnAlive)
            return 3;
        if (state is SpawnDead)
            return 2;
        if (state is SpawnNightLocked)
            return 1;
        return 0;
    }

    private static bool IsMiningNodeAvailable(MiningNode mn) =>
        mn.MyRender == null || mn.MyRender.enabled;

    private static bool TryGetCachedPositionFlag(
        Node node,
        IReadOnlyDictionary<PosKey, bool> cache,
        out bool value
    )
    {
        value = false;
        var posKey = NodePosKey(node);
        return posKey.HasValue && cache.TryGetValue(posKey.Value, out value);
    }

    private static PosKey? NodePosKey(Node node)
    {
        if (!node.X.HasValue || !node.Y.HasValue || !node.Z.HasValue)
            return null;
        return new PosKey(node.X.Value, node.Y.Value, node.Z.Value);
    }

    private static PosKey NodePosKey(Vector3 pos) => new PosKey(pos.x, pos.y, pos.z);

    // Records ambient fact deps for a live-state read. Scene("current") is always
    // relevant (the scope check filters by current zone). SourceState is recorded
    // per-node only for graph node types that map to a source key; characters have
    // no source of their own and rely on their spawn children recording via
    // GetSpawnState.
    private static void RecordLiveStateDeps(Node node)
    {
        var ambient = Engine<FactKey>.Ambient;
        if (ambient == null)
            return;

        ambient.RecordFact(new FactKey(FactKind.Scene, "current"));
        switch (node.Type)
        {
            case NodeType.SpawnPoint:
            case NodeType.MiningNode:
            case NodeType.ItemBag:
            case NodeType.Door:
                ambient.RecordFact(new FactKey(FactKind.SourceState, node.Key));
                break;
        }
    }

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

    public SpawnCategory GetCategory(Node node)
    {
        if (node == null)
            return SpawnCategory.NotApplicable;

        NodeState state;
        if (node.Type == NodeType.SpawnPoint || node.IsDirectlyPlaced)
            state = GetSpawnState(node).State;
        else if (node.Type == NodeType.Character)
            state = GetCharacterState(node).State;
        else
            return SpawnCategory.NotApplicable;

        return state switch
        {
            SpawnAlive => SpawnCategory.Alive,
            SpawnDead => SpawnCategory.Dead,
            SpawnDisabled => SpawnCategory.Disabled,
            SpawnNightLocked => SpawnCategory.NightLocked,
            SpawnUnlockBlocked => SpawnCategory.UnlockBlocked,
            _ => SpawnCategory.NotApplicable,
        };
    }
}

public readonly struct SpawnInfo
{
    public readonly NodeState State;
    public readonly SpawnPoint? LiveSpawnPoint;
    public readonly NPC? LiveNPC;
    public readonly float RespawnSeconds;

    public SpawnInfo(
        NodeState state,
        SpawnPoint? liveSpawnPoint,
        NPC? liveNPC,
        float respawnSeconds
    )
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
