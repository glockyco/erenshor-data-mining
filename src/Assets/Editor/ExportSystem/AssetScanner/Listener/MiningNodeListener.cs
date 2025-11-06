#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;
using static CoordinateRecord;

public class MiningNodeListener : IAssetScanListener<MiningNode>
{
    private readonly SQLiteConnection _db;

    public MiningNodeListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateRecord>();
        _db.CreateTable<MiningNodeRecord>();
        _db.CreateTable<MiningNodeItemRecord>();

        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.MiningNode));
        _db.DeleteAll<MiningNodeRecord>();
        _db.DeleteAll<MiningNodeItemRecord>();
    }

    public void OnScanFinished()
    {
        _db.Execute(@"
            UPDATE Coordinates
            SET MiningNodeId = (
                SELECT Id
                FROM MiningNodes
                WHERE MiningNodes.CoordinateId = Coordinates.Id
            )
            WHERE EXISTS (
                SELECT 1
                FROM MiningNodes
                WHERE MiningNodes.CoordinateId = Coordinates.Id
            );
        ");
    }

    public void OnAssetFound(MiningNode asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var coordinate = new CoordinateRecord
        {
            Scene = asset.gameObject.scene.name,
            X = asset.transform.position.x,
            Y = asset.transform.position.y,
            Z = asset.transform.position.z,
            Category = nameof(CoordinateCategory.MiningNode)
        };

        _db.Insert(coordinate);

        var miningNode = new MiningNodeRecord
        {
            CoordinateId = coordinate.Id,
            NPCName = asset.GetComponent<NPC>().NPCName,
            RespawnTime = asset.RespawnTime
        };

        _db.Insert(miningNode);
        _db.InsertAll(CreateMiningNodeItemRecords(asset, miningNode.Id));
    }

    private static List<MiningNodeItemRecord> CreateMiningNodeItemRecords(MiningNode node, int miningNodeId)
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
            MiningNodeId = miningNodeId,
            ItemStableKey = kvp.Key,
            DropChance = kvp.Value
        }).ToList();

        return itemRecords;
    }
}