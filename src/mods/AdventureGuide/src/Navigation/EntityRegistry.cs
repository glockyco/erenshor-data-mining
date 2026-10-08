using AdventureGuide.Data;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Maintains a stable-key-indexed registry of living NPCs, kept in sync by
/// Harmony patches on SpawnPoint.SpawnNPC and NPC.Start (add) and
/// Character.DoDeath (remove). Cleared on scene transitions.
///
/// Spawned NPCs are keyed by the prefab they were cloned from, matching the
/// export pipeline's "character:{name_lowered}". NPCs placed in a scene have
/// exported keys "character:{object}:{scene}:{x}:{y}:{z}" and are found by the
/// object name and position recorded when they started.
///
/// Lookups are O(1) by stable key. Stale entries (destroyed GameObjects,
/// dead NPCs missed by the death patch) are filtered out on access.
/// </summary>
public sealed class EntityRegistry
{
    private readonly struct Entry
    {
        public readonly NPC Npc;
        public readonly Character Character;

        /// <summary>Stable key for this NPC, computed at registration.</summary>
        public readonly string StableKey;

        public Entry(NPC npc, Character character, string stableKey)
        {
            Npc = npc;
            Character = character;
            StableKey = stableKey;
        }
    }

    private readonly struct Placed
    {
        public readonly Entry Entry;

        /// <summary>The scene the NPC was placed in.</summary>
        public readonly string Scene;

        /// <summary>Where the NPC stood when it started; placed NPCs may walk away.</summary>
        public readonly Vector3 Position;

        public Placed(Entry entry, string scene, Vector3 position)
        {
            Entry = entry;
            Scene = scene;
            Position = position;
        }
    }

    private readonly Dictionary<string, List<Entry>> _byKey = new(
        System.StringComparer.OrdinalIgnoreCase
    );

    // Scene-placed NPCs by lowercased scene object name. NPC.Start renames
    // them to NPCName, so neither the live name nor the live position
    // identifies the placement an exported key names.
    private readonly Dictionary<string, List<Placed>> _placedByName = new(
        System.StringComparer.OrdinalIgnoreCase
    );

    // Exported keys parsed once: a placed character's object, scene and
    // placement, or not placed. Keys come from the guide and prefab names, so
    // the set stays bounded across scenes.
    private readonly Dictionary<string, (bool Placed, PlacedCharacterKey Key)> _keyShapes = new(
        System.StringComparer.Ordinal
    );

    // Instance IDs of NPCs a SpawnPoint spawned in the current scene. Encounter
    // scripts instantiate their characters directly, so workflows use this to
    // tell an encounter's fighters from ordinary spawns of the same prefab.
    private readonly HashSet<int> _spawnPointNpcs = new();

    /// <summary>
    /// Register a newly spawned NPC. Called from SpawnPatch postfix.
    /// The spawn point is used to derive the stable key from the prefab name.
    /// For SyncFromLiveNPCs (no patch context), pass null and fall back to
    /// the NPC's GameObject name.
    /// </summary>
    public void Register(NPC npc, SpawnPoint? spawnPoint = null)
    {
        if (npc == null)
            return;
        if (spawnPoint != null)
            _spawnPointNpcs.Add(npc.GetInstanceID());
        var key = DeriveStableKey(npc, spawnPoint);
        if (key != null)
            Register(npc, key);
    }

    /// <summary>Whether a SpawnPoint spawned this NPC during the current scene.</summary>
    public bool IsSpawnPointNpc(NPC npc) => _spawnPointNpcs.Contains(npc.GetInstanceID());

    /// <summary>
    /// Register an NPC placed in the scene by the object name and position
    /// recorded before NPC.Start renamed it. Called from the NPC.Start prefix.
    /// </summary>
    public void RegisterPlaced(NPC npc)
    {
        if (npc == null || !NpcOrigins.TryGetPlacement(npc, out var objectName, out var position))
            return;
        var character = npc.GetComponent<Character>();
        if (character == null)
            return;

        var name = objectName.Trim().ToLowerInvariant();
        if (!_placedByName.TryGetValue(name, out var list))
        {
            list = new List<Placed>(1);
            _placedByName[name] = list;
        }
        int instanceId = npc.GetInstanceID();
        foreach (var placed in list)
        {
            if (placed.Entry.Npc != null && placed.Entry.Npc.GetInstanceID() == instanceId)
                return;
        }
        list.Add(
            new Placed(
                new Entry(npc, character, "character:" + name),
                npc.gameObject.scene.name,
                position
            )
        );
    }

    /// <summary>Register a scripted entity under an exported descriptor key.</summary>
    public void Register(NPC npc, string stableKey)
    {
        if (npc == null || string.IsNullOrWhiteSpace(stableKey))
            return;
        var character = npc.GetComponent<Character>();
        if (character == null)
            return;

        var key = CharacterStableKey.Normalize(stableKey);
        if (!_byKey.TryGetValue(key, out var list))
        {
            list = new List<Entry>(2);
            _byKey[key] = list;
        }
        int instanceId = npc.GetInstanceID();
        if (list.Exists(entry => entry.Npc != null && entry.Npc.GetInstanceID() == instanceId))
            return;
        list.Add(new Entry(npc, character, key));
    }

    /// <summary>
    /// Unregister a dying NPC. Called from DeathPatch postfix.
    /// </summary>
    public void Unregister(NPC npc)
    {
        if (npc == null)
            return;

        foreach (var kvp in _byKey)
        {
            var list = kvp.Value;
            for (int i = list.Count - 1; i >= 0; i--)
            {
                if (list[i].Npc == npc)
                    list.RemoveAt(i);
            }
        }
        foreach (var kvp in _placedByName)
        {
            var list = kvp.Value;
            for (int i = list.Count - 1; i >= 0; i--)
            {
                if (list[i].Entry.Npc == npc)
                    list.RemoveAt(i);
            }
        }
    }

    /// <summary>Remove all entries. Called on scene transition.</summary>
    public void Clear()
    {
        _byKey.Clear();
        _placedByName.Clear();
        _spawnPointNpcs.Clear();
    }

    /// <summary>
    /// Populate from the current NPCTable.LiveNPCs snapshot.
    /// Used on mod init (especially hot-reload) when NPCs already exist.
    /// Recovers spawn point references by scanning all SpawnPoints in the
    /// scene for matching SpawnedNPC references.
    /// </summary>
    public void SyncFromLiveNPCs()
    {
        Clear();
        if (NPCTable.LiveNPCs == null)
            return;

        // Build NPC→SpawnPoint lookup for stable key derivation
        var spawnPoints = UnityEngine.Object.FindObjectsOfType<SpawnPoint>();
        var npcToSp = new Dictionary<NPC, SpawnPoint>();
        foreach (var sp in spawnPoints)
        {
            if (sp.SpawnedNPC != null)
                npcToSp[sp.SpawnedNPC] = sp;
        }

        foreach (var npc in NPCTable.LiveNPCs)
        {
            npcToSp.TryGetValue(npc, out var sp);
            Register(npc, sp);
        }
    }

    /// <summary>
    /// Find the closest alive NPC matching the given stable key.
    /// Returns null if none alive. Prunes stale entries during iteration.
    /// </summary>
    public NPC? FindClosest(string? stableKey, Vector3 position)
    {
        if (stableKey == null)
            return null;
        // A placed character's key names one placement, not a kind of NPC.
        if (TryGetPlacedKey(stableKey, out var placedKey))
            return FindPlaced(placedKey);

        var key = CharacterStableKey.Normalize(stableKey);
        if (!_byKey.TryGetValue(key, out var list))
            return null;

        NPC? best = null;
        float bestDist = float.MaxValue;

        for (int i = list.Count - 1; i >= 0; i--)
        {
            var entry = list[i];
            if (!IsAlive(entry))
            {
                list.RemoveAt(i);
                continue;
            }

            float dist = Vector3.Distance(position, entry.Npc.transform.position);
            if (dist < bestDist)
            {
                bestDist = dist;
                best = entry.Npc;
            }
        }

        if (list.Count == 0)
            _byKey.Remove(key);

        return best;
    }

    /// <summary>
    /// Count alive NPCs matching the given stable key.
    /// Prunes stale entries during iteration.
    /// </summary>
    public int CountAlive(string? stableKey)
    {
        if (stableKey == null)
            return 0;
        if (TryGetPlacedKey(stableKey, out var placedKey))
            return FindPlaced(placedKey) != null ? 1 : 0;
        var key = CharacterStableKey.Normalize(stableKey);
        if (!_byKey.TryGetValue(key, out var list))
            return 0;

        int alive = 0;
        for (int i = list.Count - 1; i >= 0; i--)
        {
            if (!IsAlive(list[i]))
                list.RemoveAt(i);
            else
                alive++;
        }

        if (list.Count == 0)
            _byKey.Remove(key);

        return alive;
    }

    /// <summary>
    /// Whether a key names a scene placement, parsed once per key: lookups
    /// run every frame while navigating.
    /// </summary>
    private bool TryGetPlacedKey(string stableKey, out PlacedCharacterKey placedKey)
    {
        if (!_keyShapes.TryGetValue(stableKey, out var shape))
        {
            bool placed = CharacterStableKey.TryParsePlaced(stableKey, out var parsed);
            shape = (placed, parsed);
            _keyShapes[stableKey] = shape;
        }
        placedKey = shape.Key;
        return shape.Placed;
    }

    /// <summary>
    /// The live NPC placed in the key's scene that started nearest the key's
    /// placement, within the placement tolerance. Prunes stale entries during
    /// iteration.
    /// </summary>
    private NPC? FindPlaced(in PlacedCharacterKey key)
    {
        if (!_placedByName.TryGetValue(key.ObjectName, out var list))
            return null;

        var placement = new Vector3(key.X, key.Y, key.Z);
        NPC? best = null;
        float bestSqr = float.MaxValue;
        for (int i = list.Count - 1; i >= 0; i--)
        {
            var placed = list[i];
            if (!IsAlive(placed.Entry))
            {
                list.RemoveAt(i);
                continue;
            }
            if (!string.Equals(placed.Scene, key.Scene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            float sqr = (placed.Position - placement).sqrMagnitude;
            if (DirectPlacementPolicy.IsSamePlacement(sqr) && sqr < bestSqr)
            {
                bestSqr = sqr;
                best = placed.Entry.Npc;
            }
        }

        if (list.Count == 0)
            _placedByName.Remove(key.ObjectName);

        return best;
    }

    // ── Stable key derivation ───────────────────────────────────────

    /// <summary>
    /// Derive the stable key for a live NPC. Matches the format produced
    /// by StableKeyGenerator.ForCharacter in the export pipeline.
    ///
    /// Instantiated NPCs (spawn points and encounter scripts): use the prefab
    /// they were cloned from, recorded before NPC.Start renamed them.
    ///
    /// NPCs that started before the patch: use the spawn point's prefab whose
    /// NPC component has the NPC's display name.
    ///
    /// Directly placed NPCs: use the GameObject name.
    /// </summary>
    internal static string? DeriveStableKey(NPC npc, SpawnPoint? spawnPoint = null)
    {
        var clonedFrom = NpcOrigins.PrefabName(npc);
        if (clonedFrom != null)
            return CharacterStableKey.FromObjectName(clonedFrom);

        if (spawnPoint != null)
        {
            // Try CommonSpawns first, then RareSpawns
            var prefabName =
                FindPrefabName(spawnPoint.CommonSpawns, npc.NPCName)
                ?? FindPrefabName(spawnPoint.RareSpawns, npc.NPCName);
            if (prefabName != null)
                return CharacterStableKey.FromObjectName(prefabName);
        }

        // Directly placed NPC — use GameObject name
        var objName = npc.gameObject.name;
        if (string.IsNullOrEmpty(objName))
            return null;
        return CharacterStableKey.FromObjectName(objName);
    }

    /// <summary>
    /// Find the prefab name in a spawn list whose NPC component matches
    /// the given display name. Returns null if no match found.
    /// </summary>
    private static string? FindPrefabName(
        System.Collections.Generic.List<GameObject>? spawns,
        string npcName
    )
    {
        if (spawns == null)
            return null;

        foreach (var prefab in spawns)
        {
            if (prefab == null)
                continue;
            var prefabNpc = prefab.GetComponent<NPC>();
            if (
                prefabNpc != null
                && string.Equals(
                    prefabNpc.NPCName,
                    npcName,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
                return prefab.name;
        }
        return null;
    }

    private static bool IsAlive(in Entry entry)
    {
        return entry.Npc != null
            && entry.Npc.gameObject != null
            && entry.Character != null
            && entry.Character.Alive;
    }
}
