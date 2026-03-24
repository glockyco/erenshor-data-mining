using AdventureGuide.Data;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Scans the scene for loot containers (dead NPC corpses and RotChest objects)
/// that hold items needed by active quests. Both WorldMarkerSystem (global
/// markers for all quests) and NavigationController (per-quest nav priority)
/// query this shared component.
///
/// Dead NPC bodies are found via CorpseDataManager.AllCorpseData — entries
/// with non-null MyNPC are fresh kills whose bodies are still in the scene.
/// RotChests are cached once per scene load (they only spawn during
/// ZoneAnnounce.SpawnAllCorpses) and pruned per-frame as they rot away.
/// </summary>
public sealed class LootScanner
{
    /// <summary>A loot container in the scene with quest-relevant items.</summary>
    public readonly struct LootContainer
    {
        public readonly Vector3 Position;
        public readonly int InstanceId;
        /// <summary>The source Component (NPC or RotChest) for per-frame null checks.</summary>
        public readonly Component Source;
        public readonly string DisplayName;
        /// <summary>Subset of globally needed items found in this container.</summary>
        public readonly HashSet<string> MatchingItems;

        public LootContainer(Vector3 position, int instanceId, Component source,
            string displayName, HashSet<string> matchingItems)
        {
            Position = position;
            InstanceId = instanceId;
            Source = source;
            DisplayName = displayName;
            MatchingItems = matchingItems;
        }
    }

    // Rebuilt when dirty (quest/inventory/scene/death change)
    private readonly HashSet<string> _neededItems = new(System.StringComparer.OrdinalIgnoreCase);
    private readonly List<LootContainer> _containers = new();
    private bool _dirty = true;

    // RotChests cached once per scene load — pruned when destroyed
    private readonly List<RotChest> _rotChests = new();

    /// <summary>All containers with quest-relevant loot in the current scene.</summary>
    public IReadOnlyList<LootContainer> Containers => _containers;

    /// <summary>Whether the scanner found any containers on last rebuild.</summary>
    public bool HasContainers => _containers.Count > 0;

    /// <summary>Signal that quest state, inventory, or scene changed.</summary>
    public void MarkDirty() => _dirty = true;

    /// <summary>
    /// Call each frame before marker/nav queries. Prunes destroyed containers
    /// and rebuilds the container list when dirty.
    /// </summary>
    public void Update(GuideData data, QuestStateTracker state)
    {
        bool pruned = PruneDestroyed();
        if (pruned)
            _dirty = true;

        if (!_dirty) return;
        _dirty = false;
        Rebuild(data, state);
    }

    /// <summary>
    /// Called once on scene load. Captures all RotChest objects spawned by
    /// CorpseDataManager.SpawnAllCorpses(). No new RotChests appear mid-scene,
    /// so this scan is complete. Destroyed chests pruned per-frame.
    /// </summary>
    public void OnSceneLoaded()
    {
        _rotChests.Clear();
        _rotChests.AddRange(UnityEngine.Object.FindObjectsOfType<RotChest>());
        _dirty = true;
    }

    /// <summary>
    /// Find the closest container that has any item from the given set.
    /// Used by NavigationController for per-quest nav priority.
    /// </summary>
    public LootContainer? FindClosestWithAnyItem(HashSet<string> items, Vector3 playerPos)
    {
        if (items.Count == 0) return null;

        LootContainer? best = null;
        float bestDist = float.MaxValue;

        foreach (var c in _containers)
        {
            bool hasMatch = false;
            foreach (var item in c.MatchingItems)
            {
                if (items.Contains(item))
                {
                    hasMatch = true;
                    break;
                }
            }
            if (!hasMatch) continue;

            float dist = Vector3.Distance(playerPos, c.Position);
            if (dist < bestDist)
            {
                bestDist = dist;
                best = c;
            }
        }

        return best;
    }

    // ── Rebuild ──────────────────────────────────────────────────────

    private void Rebuild(GuideData data, QuestStateTracker state)
    {
        _neededItems.Clear();
        _containers.Clear();

        // 1. Build needed items from all active quests
        foreach (var quest in data.All)
        {
            if (!state.IsActive(quest.DBName)) continue;
            if (quest.RequiredItems == null) continue;
            foreach (var ri in quest.RequiredItems)
            {
                if (state.CountItemInInventory(ri.ItemName) < ri.Quantity)
                    _neededItems.Add(ri.ItemName);
            }
        }
        if (_neededItems.Count == 0) return;

        // 2. Scan dead NPCs via CorpseDataManager
        // AllCorpseData entries with non-null MyNPC are fresh kills in the
        // current scene — the NPC body is still present with its LootTable.
        foreach (var cd in CorpseDataManager.AllCorpseData)
        {
            if (cd.MyNPC == null) continue;
            var loot = cd.MyNPC.GetComponent<LootTable>();
            if (loot == null) continue;
            var matching = FindMatchingItems(loot);
            if (matching.Count > 0)
            {
                _containers.Add(new LootContainer(
                    cd.MyNPC.transform.position,
                    cd.MyNPC.GetInstanceID(),
                    cd.MyNPC,
                    cd.MyNPC.NPCName,
                    matching));
            }
        }

        // 3. Scan RotChests cached at scene load
        foreach (var chest in _rotChests)
        {
            if (chest == null) continue;
            var loot = chest.GetComponent<LootTable>();
            if (loot == null) continue;
            var matching = FindMatchingItems(loot);
            if (matching.Count > 0)
            {
                _containers.Add(new LootContainer(
                    chest.transform.position,
                    chest.GetInstanceID(),
                    chest,
                    "Loot Chest",
                    matching));
            }
        }
    }

    private HashSet<string> FindMatchingItems(LootTable loot)
    {
        var result = new HashSet<string>(System.StringComparer.OrdinalIgnoreCase);
        foreach (var item in loot.ActualDrops)
        {
            if (item != null && !string.IsNullOrEmpty(item.ItemName)
                && _neededItems.Contains(item.ItemName))
            {
                result.Add(item.ItemName);
            }
        }
        return result;
    }

    // ── Per-frame pruning ────────────────────────────────────────────

    /// <summary>
    /// Remove containers whose source was destroyed (Unity fake-null) and
    /// prune cached RotChests that have been destroyed. Returns true if
    /// anything was removed.
    /// </summary>
    private bool PruneDestroyed()
    {
        bool removed = false;

        for (int i = _containers.Count - 1; i >= 0; i--)
        {
            if (_containers[i].Source == null)
            {
                _containers.RemoveAt(i);
                removed = true;
            }
        }

        for (int i = _rotChests.Count - 1; i >= 0; i--)
        {
            if (_rotChests[i] == null)
                _rotChests.RemoveAt(i);
        }

        return removed;
    }
}
