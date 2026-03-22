using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Maintains a name-indexed registry of living NPCs, kept in sync by Harmony
/// patches on SpawnPoint.SpawnNPC (add) and Character.DoDeath (remove).
/// Cleared on scene transitions.
///
/// Lookups are O(1) by NPC display name. Stale entries (destroyed GameObjects,
/// dead NPCs missed by the death patch — e.g. night despawn) are filtered out
/// on access and pruned lazily.
///
/// Character components are cached at registration to avoid per-frame
/// GetComponent calls in the IsAlive check.
/// </summary>
public sealed class EntityRegistry
{
    /// <summary>NPC + cached Character component to avoid per-frame GetComponent.</summary>
    private readonly struct Entry
    {
        public readonly NPC Npc;
        public readonly Character Character;
        public Entry(NPC npc, Character character) { Npc = npc; Character = character; }
    }

    private readonly Dictionary<string, List<Entry>> _byName = new(System.StringComparer.OrdinalIgnoreCase);

    /// <summary>
    /// Register a newly spawned NPC. Called from SpawnPatch postfix.
    /// </summary>
    public void Register(NPC npc)
    {
        if (npc == null) return;
        string name = npc.NPCName;
        if (string.IsNullOrEmpty(name)) return;

        var character = npc.GetComponent<Character>();
        if (character == null) return;

        if (!_byName.TryGetValue(name, out var list))
        {
            list = new List<Entry>(2);
            _byName[name] = list;
        }
        list.Add(new Entry(npc, character));
    }

    /// <summary>
    /// Unregister a dying NPC. Called from DeathPatch postfix.
    /// </summary>
    public void Unregister(NPC npc)
    {
        if (npc == null) return;
        string name = npc.NPCName;
        if (string.IsNullOrEmpty(name)) return;

        if (_byName.TryGetValue(name, out var list))
        {
            for (int i = list.Count - 1; i >= 0; i--)
                if (list[i].Npc == npc)
                    list.RemoveAt(i);
            if (list.Count == 0)
                _byName.Remove(name);
        }
    }

    /// <summary>
    /// Remove all entries. Called on scene transition.
    /// </summary>
    public void Clear() => _byName.Clear();

    /// <summary>
    /// Populate from the current NPCTable.LiveNPCs snapshot.
    /// Used on mod init (especially hot-reload) when NPCs already exist.
    /// </summary>
    public void SyncFromLiveNPCs()
    {
        Clear();
        if (NPCTable.LiveNPCs == null) return;
        foreach (var npc in NPCTable.LiveNPCs)
            Register(npc);
    }

    /// <summary>
    /// Find the closest alive NPC with the given display name to a world position.
    /// Returns null if none alive. Prunes stale entries during iteration.
    /// </summary>
    public NPC? FindClosest(string? displayName, Vector3 position)
    {
        if (displayName == null || !_byName.TryGetValue(displayName, out var list))
            return null;

        NPC? best = null;
        float bestDist = float.MaxValue;

        for (int i = list.Count - 1; i >= 0; i--)
        {
            var entry = list[i];

            // Prune stale: destroyed GameObject or dead NPC
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
            _byName.Remove(displayName);

        return best;
    }

    /// <summary>
    /// Count alive NPCs with the given display name.
    /// Prunes stale entries during iteration.
    /// </summary>
    public int CountAlive(string? displayName)
    {
        if (displayName == null || !_byName.TryGetValue(displayName, out var list))
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
            _byName.Remove(displayName);

        return alive;
    }

    private static bool IsAlive(in Entry entry)
    {
        return entry.Npc != null
            && entry.Npc.gameObject != null
            && entry.Character != null
            && entry.Character.Alive;
    }
}
