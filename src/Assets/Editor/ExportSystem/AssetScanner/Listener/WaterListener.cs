#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;
using static CoordinateRecord;

public class WaterListener : IAssetScanListener<Water>
{
    private readonly SQLiteConnection _db;

    public WaterListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateRecord>();
        _db.CreateTable<WaterRecord>();
        _db.CreateTable<WaterFishableRecord>();
        
        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.Water));
        _db.DeleteAll<WaterRecord>();
        _db.DeleteAll<WaterFishableRecord>();
    }
    
    public void OnScanFinished()
    {
        _db.Execute(@"
            UPDATE Coordinates
            SET WaterId = (
                SELECT Id
                FROM Waters
                WHERE Waters.CoordinateId = Coordinates.Id
            )
            WHERE EXISTS (
                SELECT 1
                FROM Waters
                WHERE Waters.CoordinateId = Coordinates.Id
            );
        ");
    }

    public void OnAssetFound(Water asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");
        
        var coordinate = new CoordinateRecord
        {
            Scene = asset.gameObject.scene.name,
            X = asset.transform.position.x,
            Y = asset.transform.position.y,
            Z = asset.transform.position.z,
            Category = nameof(CoordinateCategory.Water)
        };

        _db.Insert(coordinate);

        var water = new WaterRecord
        {
            CoordinateId = coordinate.Id,
            Width = asset.transform.localScale.x,
            Height = asset.transform.localScale.y,
            Depth = asset.transform.localScale.z
        };

        _db.Insert(water);
        _db.InsertAll(CreateWaterFishableRecords(asset, water.Id));
    }

    private static List<WaterFishableRecord> CreateWaterFishableRecords(Water water, int waterId)
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
                    WaterId = waterId,
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