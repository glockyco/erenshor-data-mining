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
/// </summary>
public sealed class EntityRegistry
{
    private readonly Dictionary<string, List<NPC>> _byName = new(System.StringComparer.OrdinalIgnoreCase);

    /// <summary>
    /// Register a newly spawned NPC. Called from SpawnPatch postfix.
    /// </summary>
    public void Register(NPC npc)
    {
        if (npc == null) return;
        string name = npc.NPCName;
        if (string.IsNullOrEmpty(name)) return;

        if (!_byName.TryGetValue(name, out var list))
        {
            list = new List<NPC>(2);
            _byName[name] = list;
        }
        list.Add(npc);
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
            list.Remove(npc);
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
            var npc = list[i];

            // Prune stale: destroyed GameObject or dead NPC
            if (!IsAlive(npc))
            {
                list.RemoveAt(i);
                continue;
            }

            float dist = Vector3.Distance(position, npc.transform.position);
            if (dist < bestDist)
            {
                bestDist = dist;
                best = npc;
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

    private static bool IsAlive(NPC? npc)
    {
        if (npc == null || npc.gameObject == null) return false;
        var character = npc.GetComponent<Character>();
        return character != null && character.Alive;
    }
}
