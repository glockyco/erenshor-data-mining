using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Maintains a stable-key-indexed registry of living NPCs, kept in sync by
/// Harmony patches on SpawnPoint.SpawnNPC (add) and Character.DoDeath (remove).
/// Cleared on scene transitions.
///
/// Stable keys are derived from the character prefab name (for spawned NPCs)
/// or the GameObject name (for directly placed NPCs), matching the format used
/// by the export pipeline: "character:{name_lowered}".
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

    private readonly Dictionary<string, List<Entry>> _byKey = new(System.StringComparer.OrdinalIgnoreCase);

    /// <summary>
    /// Register a newly spawned NPC. Called from SpawnPatch postfix.
    /// The spawn point is used to derive the stable key from the prefab name.
    /// For SyncFromLiveNPCs (no patch context), pass null and fall back to
    /// the NPC's GameObject name.
    /// </summary>
    public void Register(NPC npc, SpawnPoint? spawnPoint = null)
    {
        if (npc == null) return;

        var character = npc.GetComponent<Character>();
        if (character == null) return;

        string? key = DeriveStableKey(npc, spawnPoint);
        if (key == null) return;

        if (!_byKey.TryGetValue(key, out var list))
        {
            list = new List<Entry>(2);
            _byKey[key] = list;
        }
        list.Add(new Entry(npc, character, key));
    }

    /// <summary>
    /// Unregister a dying NPC. Called from DeathPatch postfix.
    /// </summary>
    public void Unregister(NPC npc)
    {
        if (npc == null) return;

        // We don't know the key, so scan all lists for this instance.
        // Death is infrequent so this is fine.
        foreach (var kvp in _byKey)
        {
            var list = kvp.Value;
            for (int i = list.Count - 1; i >= 0; i--)
            {
                if (list[i].Npc == npc)
                {
                    list.RemoveAt(i);
                    break;
                }
            }
        }
    }

    /// <summary>Remove all entries. Called on scene transition.</summary>
    public void Clear() => _byKey.Clear();

    /// <summary>
    /// Populate from the current NPCTable.LiveNPCs snapshot.
    /// Used on mod init (especially hot-reload) when NPCs already exist.
    /// Recovers spawn point references by scanning all SpawnPoints in the
    /// scene for matching SpawnedNPC references.
    /// </summary>
    public void SyncFromLiveNPCs()
    {
        Clear();
        if (NPCTable.LiveNPCs == null) return;

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
        if (stableKey == null) return null;

        // Try exact key first, then base key without variant suffix.
        // The export pipeline deduplicates identical prefab names by
        // appending :N (e.g. "character:foo:1"), but runtime entities
        // register under the base key ("character:foo").
        if (!_byKey.TryGetValue(stableKey, out var list))
        {
            var baseKey = StripVariantSuffix(stableKey);
            if (baseKey == null || !_byKey.TryGetValue(baseKey, out list))
                return null;
        }

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
            _byKey.Remove(stableKey);

        return best;
    }

    /// <summary>
    /// Count alive NPCs matching the given stable key.
    /// Prunes stale entries during iteration.
    /// </summary>
    public int CountAlive(string? stableKey)
    {
        if (stableKey == null) return 0;
        if (!_byKey.TryGetValue(stableKey, out var list))
        {
            var baseKey = StripVariantSuffix(stableKey);
            if (baseKey == null || !_byKey.TryGetValue(baseKey, out list))
                return 0;
        }

        int alive = 0;
        for (int i = list.Count - 1; i >= 0; i--)
        {
            if (!IsAlive(list[i]))
                list.RemoveAt(i);
            else
                alive++;
        }

        if (list.Count == 0)
            _byKey.Remove(stableKey);

        return alive;
    }

    // ── Stable key derivation ───────────────────────────────────────

    /// <summary>
    /// Derive the stable key for a live NPC. Matches the format produced
    /// by StableKeyGenerator.ForCharacter in the export pipeline.
    ///
    /// Spawned NPCs: use the prefab name from the spawn point. For
    /// multi-CommonSpawn points, match the NPC's display name against
    /// prefab NPC components to find the correct prefab.
    ///
    /// Directly placed NPCs: use the GameObject name.
    /// </summary>
    internal static string? DeriveStableKey(NPC npc, SpawnPoint? spawnPoint = null)
    {
        if (spawnPoint != null)
        {
            // Try CommonSpawns first, then RareSpawns
            var prefabName = FindPrefabName(spawnPoint.CommonSpawns, npc.NPCName)
                          ?? FindPrefabName(spawnPoint.RareSpawns, npc.NPCName);
            if (prefabName != null)
                return "character:" + prefabName.Trim().ToLowerInvariant();
        }

        // Directly placed NPC — use GameObject name
        var objName = npc.gameObject.name;
        if (string.IsNullOrEmpty(objName)) return null;
        return "character:" + objName.Trim().ToLowerInvariant();
    }

    /// <summary>
    /// Find the prefab name in a spawn list whose NPC component matches
    /// the given display name. Returns null if no match found.
    /// </summary>
    private static string? FindPrefabName(System.Collections.Generic.List<GameObject>? spawns, string npcName)
    {
        if (spawns == null) return null;

        foreach (var prefab in spawns)
        {
            if (prefab == null) continue;
            var prefabNpc = prefab.GetComponent<NPC>();
            if (prefabNpc != null && string.Equals(prefabNpc.NPCName, npcName,
                    System.StringComparison.OrdinalIgnoreCase))
                return prefab.name;
        }
        return null;
    }

    /// <summary>
    /// Strip the export pipeline's variant suffix from a stable key.
    /// "character:foo:1" → "character:foo". Returns null if the key
    /// has no variant suffix (i.e., only one colon for the character: prefix).
    /// </summary>
    private static string? StripVariantSuffix(string key)
    {
        // character:name → 1 colon (prefix), no variant
        // character:name:1 → 2 colons, strip last segment
        int lastColon = key.LastIndexOf(':');
        if (lastColon <= 0) return null;
        // Check that the segment after the last colon is numeric
        var suffix = key.AsSpan(lastColon + 1);
        if (suffix.Length == 0) return null;
        foreach (char c in suffix)
        {
            if (c < '0' || c > '9') return null;
        }
        // Ensure there's still a colon before this one (the character: prefix)
        var baseKey = key.Substring(0, lastColon);
        return baseKey.IndexOf(':') >= 0 ? baseKey : null;
    }

    private static bool IsAlive(in Entry entry)
    {
        return entry.Npc != null
            && entry.Npc.gameObject != null
            && entry.Character != null
            && entry.Character.Alive;
    }
}
