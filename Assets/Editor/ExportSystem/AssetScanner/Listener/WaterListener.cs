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

        void AddFishableRecords(List<Item> fishables, string type)
        {
            if (fishables is not { Count: > 0 })
            {
                return;
            }

            var mapFragmentChance = 5f;
            var fishableChance = 95f / fishables.Count;

            var itemTotalDropChances = new Dictionary<string, float>();
            foreach (var item in fishables.Where(i => i != null))
            {
                itemTotalDropChances.TryAdd(item.ItemName, 0f);
                itemTotalDropChances[item.ItemName] += fishableChance;
            }

            var index = 0;
            foreach (var item in fishables.Where(i => i != null))
            {
                var itemRecord = new WaterFishableDBRecord
                {
                    WaterId = waterId,
                    Type = type,
                    Index = index++,
                    ItemId = item.Id,
                    ItemName = item.ItemName,
                    DropChance = fishableChance,
                    TotalDropChance = itemTotalDropChances[item.ItemName],
                };
                waterFishableRecords.Add(itemRecord);
            }

            // Add the map fragment record
            waterFishableRecords.Add(new WaterFishableDBRecord
            {
                WaterId = waterId,
                Type = type,
                Index = -1, // Use -1 or a special value for the map fragment
                ItemId = null,
                ItemName = "A random Torn Treasure Map fragment.",
                DropChance = mapFragmentChance,
                TotalDropChance = mapFragmentChance,
            });
        }

        AddFishableRecords(water.DayFishables, "DayFishable");
        AddFishableRecords(water.NightFishables, "NightFishable");

        return waterFishableRecords;
    }
}