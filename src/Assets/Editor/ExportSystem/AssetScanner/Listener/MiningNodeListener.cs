#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;

public class MiningNodeListener : IAssetScanListener<MiningNode>
{
    private readonly SQLiteConnection _db;
    private readonly List<MiningNodeRecord> _miningNodeRecords = new();
    private readonly List<MiningNodeItemRecord> _miningNodeItemRecords = new();
    private readonly DuplicateKeyTracker _keyTracker = new("MiningNodeListener");

    public MiningNodeListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<MiningNodeRecord>();
        _db.CreateTable<MiningNodeItemRecord>();

        _db.DeleteAll<MiningNodeRecord>();
        _db.DeleteAll<MiningNodeItemRecord>();

        _miningNodeRecords.Clear();
        _miningNodeItemRecords.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_miningNodeRecords);
        _db.InsertAll(_miningNodeItemRecords);

        _miningNodeRecords.Clear();
        _miningNodeItemRecords.Clear();
    }

    public void OnAssetFound(MiningNode asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var scene = asset.gameObject.scene.name;
        var x = asset.transform.position.x;
        var y = asset.transform.position.y;
        var z = asset.transform.position.z;

        var baseStableKey = StableKeyGenerator.ForMiningNode(scene, x, y, z);
        var stableKey = _keyTracker.GetUniqueKey(baseStableKey, asset.gameObject.name);

        var miningNode = new MiningNodeRecord
        {
            StableKey = stableKey,
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            NPCName = asset.GetComponent<NPC>().NPCName,
            RespawnTime = asset.RespawnTime,
        };

        _miningNodeRecords.Add(miningNode);
        _miningNodeItemRecords.AddRange(CreateMiningNodeItemRecords(asset, stableKey));
    }

    private static List<MiningNodeItemRecord> CreateMiningNodeItemRecords(
        MiningNode node,
        string miningNodeStableKey
    )
    {
        // code-fact: mining.outcome_roll
        // code-fact: mining.roll_range
        // Percent per mined node at the standard runtime rate.
        const float guaranteeChance = 20f;
        const float commonChance = 55f;
        const float rareChance = 21f;
        const float legendChance = 4f;

        var itemTotalDropChances = new Dictionary<string, float>();

        // code-fact: mining.guarantee_fallback
        var guaranteeItem = node.guarantee ?? GameData.GM?.GuaranteeMine;
        if (guaranteeItem == null || string.IsNullOrEmpty(guaranteeItem.name))
        {
            throw new System.InvalidOperationException(
                $"Mining node {miningNodeStableKey} has no resolvable guarantee item. "
                    + "Export requires its serialized guarantee or an available GameManager.GuaranteeMine."
            );
        }

        void AddItem(Item? item, float chance)
        {
            if (item == null || string.IsNullOrEmpty(item.name))
            {
                return;
            }
            var key = StableKeyGenerator.ForItem(item);
            itemTotalDropChances.TryAdd(key, 0f);
            itemTotalDropChances[key] += chance;
        }

        // code-fact: mining.empty_common_fallback
        // code-fact: mining.empty_rare_fallback
        // code-fact: mining.empty_legend_fallback
        void AddPool(List<Item> pool, float chance)
        {
            if (pool.Count == 0)
            {
                AddItem(guaranteeItem, chance);
                return;
            }
            // Null slots retain their share rather than increasing other items' chances.
            var perSlot = chance / pool.Count;
            foreach (var item in pool)
            {
                AddItem(item, perSlot);
            }
        }

        AddItem(guaranteeItem, guaranteeChance);
        AddPool(node.Common, commonChance);
        AddPool(node.Rare, rareChance);
        AddPool(node.Legend, legendChance);

        // Create one record per item
        var itemRecords = itemTotalDropChances
            .Select(kvp => new MiningNodeItemRecord
            {
                MiningNodeStableKey = miningNodeStableKey,
                ItemStableKey = kvp.Key,
                DropChance = kvp.Value,
            })
            .ToList();

        return itemRecords;
    }
}
