#nullable enable

using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class MiningNodeListener : IAssetScanListener<MiningNode>
{
    public readonly List<MiningNodeDBRecord> Records = new();
    public readonly List<MiningNodeItemDBRecord> ItemRecords = new();

    public void OnAssetFound(MiningNode asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var id = asset.gameObject.scene.name + asset.transform.position;

        var record = new MiningNodeDBRecord
        {
            Id = id,
            SceneName = asset.gameObject.scene.name,
            PositionX = asset.transform.position.x,
            PositionY = asset.transform.position.y,
            PositionZ = asset.transform.position.z,
            RespawnTime = asset.RespawnTime
        };

        Records.Add(record);

        ItemRecords.AddRange(ProcessMiningNodeItems(asset, id));
    }

    public void Reset() => Records.Clear();

    private static List<MiningNodeItemDBRecord> ProcessMiningNodeItems(MiningNode node, string miningNodeId)
    {
        // Calculate drop chances based on the logic in MiningNode.Mine()
        // Legend = 96-99, Rare = 75-95, Common = 20-75, Guarantee = 0-19
        const float guaranteeChance = 20.00f; // 20 - 0 = 20
        const float commonChance = 55.00f; // 75 - 20 = 55
        const float rareChance = 21.00f; // 96 - 75 = 21
        const float legendChance = 4.00f; // 100 - 96 = 4

        var itemTotalDropChances = new Dictionary<string, float>();
        var itemRecords = new List<MiningNodeItemDBRecord>();

        // --- Calculate Total Drop Chances First ---

        // Guarantee
        var guaranteeItem = node.guarantee ?? GameData.GM?.GuaranteeMine;
        if (guaranteeItem != null)
        {
            itemTotalDropChances.TryAdd(guaranteeItem.ItemName, 0f);
            itemTotalDropChances[guaranteeItem.ItemName] += guaranteeChance;
        }

        // Common
        if (node.Common is { Count: > 0 })
        {
            var dropChancePerItem = commonChance / node.Common.Count;
            foreach (var item in node.Common.Where(i => i != null))
            {
                itemTotalDropChances.TryAdd(item.ItemName, 0f);
                itemTotalDropChances[item.ItemName] += dropChancePerItem;
            }
        }

        // Rare
        if (node.Rare is { Count: > 0 })
        {
            var dropChancePerItem = rareChance / node.Rare.Count;
            foreach (var item in node.Rare.Where(i => i != null))
            {
                itemTotalDropChances.TryAdd(item.ItemName, 0f);
                itemTotalDropChances[item.ItemName] += dropChancePerItem;
            }
        }

        // Legend
        if (node.Legend is { Count: > 0 })
        {
            var dropChancePerItem = legendChance / node.Legend.Count;
            foreach (var item in node.Legend.Where(i => i != null))
            {
                itemTotalDropChances.TryAdd(item.ItemName, 0f);
                itemTotalDropChances[item.ItemName] += dropChancePerItem;
            }
        }

        // --- Create Records with Rarity Indices ---
        int guaranteeIndex = 0;
        int commonIndex = 0;
        int rareIndex = 0;
        int legendIndex = 0;

        // Process guarantee item
        if (guaranteeItem != null)
        {
            var guaranteeRecord = new MiningNodeItemDBRecord
            {
                MiningNodeId = miningNodeId,
                Rarity = "Guarantee",
                RarityIndex = guaranteeIndex++,
                ItemName = guaranteeItem.ItemName,
                DropChance = guaranteeChance,
                TotalDropChance = itemTotalDropChances.GetValueOrDefault(guaranteeItem.ItemName, 0f),
            };
            itemRecords.Add(guaranteeRecord);
        }

        // Process common items
        if (node.Common is { Count: > 0 })
        {
            var dropChancePerItem = commonChance / node.Common.Count;
            foreach (var item in node.Common.Where(i => i != null))
            {
                var itemRecord = new MiningNodeItemDBRecord
                {
                    MiningNodeId = miningNodeId,
                    Rarity = "Common",
                    RarityIndex = commonIndex++,
                    ItemName = item.ItemName,
                    DropChance = dropChancePerItem,
                    TotalDropChance = itemTotalDropChances.GetValueOrDefault(item.ItemName, 0f),
                };
                itemRecords.Add(itemRecord);
            }
        }

        // Process rare items
        if (node.Rare is { Count: > 0 })
        {
            var dropChancePerItem = rareChance / node.Rare.Count;
            foreach (var item in node.Rare.Where(i => i != null))
            {
                var itemRecord = new MiningNodeItemDBRecord
                {
                    MiningNodeId = miningNodeId,
                    Rarity = "Rare",
                    RarityIndex = rareIndex++,
                    ItemName = item.ItemName,
                    DropChance = dropChancePerItem,
                    TotalDropChance = itemTotalDropChances.GetValueOrDefault(item.ItemName, 0f),
                };
                itemRecords.Add(itemRecord);
            }
        }

        // Process legend items
        if (node.Legend is { Count: > 0 })
        {
            var dropChancePerItem = legendChance / node.Legend.Count;
            foreach (var item in node.Legend.Where(i => i != null))
            {
                var itemRecord = new MiningNodeItemDBRecord
                {
                    MiningNodeId = miningNodeId,
                    Rarity = "Legend",
                    RarityIndex = legendIndex++,
                    ItemName = item.ItemName,
                    DropChance = dropChancePerItem,
                    TotalDropChance = itemTotalDropChances.GetValueOrDefault(item.ItemName, 0f),
                };
                itemRecords.Add(itemRecord);
            }
        }

        return itemRecords;
    }
}