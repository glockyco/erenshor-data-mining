#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;

public class WaterListener : IAssetScanListener<Water>
{
    private readonly SQLiteConnection _db;
    private readonly List<WaterDBRecord> _waterRecords = new();
    private readonly List<WaterFishableDBRecord> _waterFishableRecords = new();

    public WaterListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<WaterDBRecord>();
        _db.CreateTable<WaterFishableDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<WaterDBRecord>();
            _db.DeleteAll<WaterFishableDBRecord>();
            _db.InsertAll(_waterRecords);
            _db.InsertAll(_waterFishableRecords);
        });
        _waterRecords.Clear();
        _waterFishableRecords.Clear();
    }

    public void OnAssetFound(Water asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var waterIndex = _waterRecords.Count;
        var record = new WaterDBRecord
        {
            Id = $"{asset.gameObject.scene.name}({waterIndex})",
            SceneName = asset.gameObject.scene.name,
            Index = waterIndex,
        };

        _waterRecords.Add(record);

        _waterFishableRecords.AddRange(CreateWaterFishableRecords(asset, record.Id));
    }

    private static List<WaterFishableDBRecord> CreateWaterFishableRecords(Water water, string waterId)
    {
        var waterFishableRecords = new List<WaterFishableDBRecord>();

        // DayFishables
        if (water.DayFishables is { Count: > 0 })
        {
            var dropChancePerItem = 100f / water.DayFishables.Count;
            var itemTotalDropChances = new Dictionary<string, float>();
            foreach (var item in water.DayFishables.Where(i => i != null))
            {
                itemTotalDropChances.TryAdd(item.ItemName, 0f);
                itemTotalDropChances[item.ItemName] += dropChancePerItem;
            }

            var index = 0;
            foreach (var item in water.DayFishables.Where(i => i != null))
            {
                var itemRecord = new WaterFishableDBRecord
                {
                    WaterId = waterId,
                    Type = "DayFishable",
                    Index = index++,
                    ItemId = item.Id,
                    ItemName = item.ItemName,
                    DropChance = 100f / water.DayFishables.Count,
                    TotalDropChance = itemTotalDropChances[item.ItemName],
                };
                waterFishableRecords.Add(itemRecord);
            }
        }

        // NightFishables
        if (water.NightFishables is { Count: > 0 })
        {
            var dropChancePerItem = 100f / water.NightFishables.Count;
            var itemTotalDropChances = new Dictionary<string, float>();
            foreach (var item in water.NightFishables.Where(i => i != null))
            {
                itemTotalDropChances.TryAdd(item.ItemName, 0f);
                itemTotalDropChances[item.ItemName] += dropChancePerItem;
            }

            var index = 0;
            foreach (var item in water.NightFishables.Where(i => i != null))
            {
                var itemRecord = new WaterFishableDBRecord
                {
                    WaterId = waterId,
                    Type = "NightFishable",
                    Index = index++,
                    ItemId = item.Id,
                    ItemName = item.ItemName,
                    DropChance = 100f / water.NightFishables.Count,
                    TotalDropChance = itemTotalDropChances[item.ItemName],
                };
                waterFishableRecords.Add(itemRecord);
            }
        }

        return waterFishableRecords;
    }
}