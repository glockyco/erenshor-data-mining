#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;

public class MiningNodeListener : IAssetScanListener<MiningNode>
{
    private readonly SQLiteConnection _db;

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
    }

    public void OnScanFinished()
    {
        // No post-processing needed
    }

    public void OnAssetFound(MiningNode asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var scene = asset.gameObject.scene.name;
        var x = asset.transform.position.x;
        var y = asset.transform.position.y;
        var z = asset.transform.position.z;
        var stableKey = StableKeyGenerator.ForMiningNode(scene, x, y, z);

        var miningNode = new MiningNodeRecord
        {
            StableKey = stableKey,
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            NPCName = asset.GetComponent<NPC>().NPCName,
            RespawnTime = asset.RespawnTime
        };

        _db.Insert(miningNode);
        _db.InsertAll(CreateMiningNodeItemRecords(asset, stableKey));
    }

    private static List<MiningNodeItemRecord> CreateMiningNodeItemRecords(MiningNode node, string miningNodeStableKey)
    {
        // Calculate drop chances based on the logic in MiningNode.Mine()
        // Legend = 96-99, Rare = 75-95, Common = 20-75, Guarantee = 0-19
        const float guaranteeChance = 20.00f; // 20 - 0 = 20
        const float commonChance = 55.00f; // 75 - 20 = 55
        const float rareChance = 21.00f; // 96 - 75 = 21
        const float legendChance = 4.00f; // 100 - 96 = 4

        var itemTotalDropChances = new Dictionary<string, float>();

        // Guarantee
        var guaranteeItem = node.guarantee ?? GameData.GM?.GuaranteeMine;
        if (guaranteeItem != null && !string.IsNullOrEmpty(guaranteeItem.name))
        {
            var itemStableKey = StableKeyGenerator.ForItem(guaranteeItem);
            itemTotalDropChances.TryAdd(itemStableKey, 0f);
            itemTotalDropChances[itemStableKey] += guaranteeChance;
        }

        // Common
        if (node.Common is { Count: > 0 })
        {
            var dropChancePerItem = commonChance / node.Common.Count;
            foreach (var item in node.Common.Where(i => i != null && !string.IsNullOrEmpty(i.name)))
            {
                var itemStableKey = StableKeyGenerator.ForItem(item);
                itemTotalDropChances.TryAdd(itemStableKey, 0f);
                itemTotalDropChances[itemStableKey] += dropChancePerItem;
            }
        }

        // Rare
        if (node.Rare is { Count: > 0 })
        {
            var dropChancePerItem = rareChance / node.Rare.Count;
            foreach (var item in node.Rare.Where(i => i != null && !string.IsNullOrEmpty(i.name)))
            {
                var itemStableKey = StableKeyGenerator.ForItem(item);
                itemTotalDropChances.TryAdd(itemStableKey, 0f);
                itemTotalDropChances[itemStableKey] += dropChancePerItem;
            }
        }

        // Legend
        if (node.Legend is { Count: > 0 })
        {
            var dropChancePerItem = legendChance / node.Legend.Count;
            foreach (var item in node.Legend.Where(i => i != null && !string.IsNullOrEmpty(i.name)))
            {
                var itemStableKey = StableKeyGenerator.ForItem(item);
                itemTotalDropChances.TryAdd(itemStableKey, 0f);
                itemTotalDropChances[itemStableKey] += dropChancePerItem;
            }
        }

        // Create one record per item
        var itemRecords = itemTotalDropChances.Select(kvp => new MiningNodeItemRecord
        {
            MiningNodeStableKey = miningNodeStableKey,
            ItemStableKey = kvp.Key,
            DropChance = kvp.Value
        }).ToList();

        return itemRecords;
    }
}
