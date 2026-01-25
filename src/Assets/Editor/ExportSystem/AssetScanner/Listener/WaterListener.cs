#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;

public class WaterListener : IAssetScanListener<Water>
{
    private readonly SQLiteConnection _db;
    private readonly List<WaterRecord> _waterRecords = new();
    private readonly List<WaterFishableRecord> _waterFishableRecords = new();
    private readonly DuplicateKeyTracker _keyTracker = new("WaterListener");

    public WaterListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<WaterRecord>();
        _db.CreateTable<WaterFishableRecord>();

        _db.DeleteAll<WaterRecord>();
        _db.DeleteAll<WaterFishableRecord>();

        _waterRecords.Clear();
        _waterFishableRecords.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_waterRecords);
        _db.InsertAll(_waterFishableRecords);

        _waterRecords.Clear();
        _waterFishableRecords.Clear();
    }

    public void OnAssetFound(Water asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var scene = asset.gameObject.scene.name;
        var x = asset.transform.position.x;
        var y = asset.transform.position.y;
        var z = asset.transform.position.z;

        var baseStableKey = StableKeyGenerator.ForWater(scene, x, y, z);
        var stableKey = _keyTracker.GetUniqueKey(baseStableKey, asset.gameObject.name);

        var water = new WaterRecord
        {
            StableKey = stableKey,
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            Width = asset.transform.localScale.x,
            Height = asset.transform.localScale.y,
            Depth = asset.transform.localScale.z
        };

        _waterRecords.Add(water);
        _waterFishableRecords.AddRange(CreateWaterFishableRecords(asset, stableKey));
    }

    private static List<WaterFishableRecord> CreateWaterFishableRecords(Water water, string waterStableKey)
    {
        var waterFishableRecords = new List<WaterFishableRecord>();

        // Treasure map piece stable keys (normalized item names)
        var treasureMapPieceStableKeys = new List<string>
        {
            "item:torn treasure map (top right)",
            "item:torn treasure map (top left)",
            "item:torn treasure map (bottom right)",
            "item:torn treasure map (bottom left)"
        };

        void AddFishableRecords(List<Item> fishables, string type)
        {
            if (fishables is not { Count: > 0 })
            {
                return;
            }

            var mapFragmentChance = 5f;
            var fishableChance = 95f / fishables.Count;

            var itemTotalDropChances = new Dictionary<string, float>();
            foreach (var item in fishables.Where(i => i != null && !string.IsNullOrEmpty(i.name)))
            {
                var itemStableKey = StableKeyGenerator.ForItem(item);
                itemTotalDropChances.TryAdd(itemStableKey, 0f);
                itemTotalDropChances[itemStableKey] += fishableChance;
            }
            foreach (var itemStableKey in treasureMapPieceStableKeys)
            {
                itemTotalDropChances.TryAdd(itemStableKey, 0f);
                itemTotalDropChances[itemStableKey] += mapFragmentChance / treasureMapPieceStableKeys.Count;
            }

            foreach (var kvp in itemTotalDropChances)
            {
                waterFishableRecords.Add(new WaterFishableRecord
                {
                    WaterStableKey = waterStableKey,
                    Type = type,
                    ItemStableKey = kvp.Key,
                    DropChance = kvp.Value
                });
            }
        }

        AddFishableRecords(water.DayFishables, "DayFishable");
        AddFishableRecords(water.NightFishables, "NightFishable");

        return waterFishableRecords;
    }
}
