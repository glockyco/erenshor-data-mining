#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;
using static CoordinateDBRecord;

public class WaterListener : IAssetScanListener<Water>
{
    private readonly SQLiteConnection _db;

    public WaterListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateDBRecord>();
        _db.CreateTable<WaterDBRecord>();
        _db.CreateTable<WaterFishableDBRecord>();
        
        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.Water));
        _db.DeleteAll<WaterDBRecord>();
        _db.DeleteAll<WaterFishableDBRecord>();
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
        
        var coordinate = new CoordinateDBRecord
        {
            Scene = asset.gameObject.scene.name,
            X = asset.transform.position.x,
            Y = asset.transform.position.y,
            Z = asset.transform.position.z,
            Category = nameof(CoordinateCategory.Water)
        };

        _db.Insert(coordinate);

        var water = new WaterDBRecord
        {
            CoordinateId = coordinate.Id,
        };

        _db.Insert(water);
        _db.InsertAll(CreateWaterFishableRecords(asset, water.Id));
    }

    private static List<WaterFishableDBRecord> CreateWaterFishableRecords(Water water, int waterId)
    {
        var waterFishableRecords = new List<WaterFishableDBRecord>();

        var treasureMapPieces = new List<string>
        {
            "Torn Treasure Map (Top Right)",
            "Torn Treasure Map (Top Left)",
            "Torn Treasure Map (Bottom Right)",
            "Torn Treasure Map (Bottom Left)"
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
            foreach (var item in fishables.Where(i => i != null))
            {
                itemTotalDropChances.TryAdd(item.ItemName, 0f);
                itemTotalDropChances[item.ItemName] += fishableChance;
            }
            foreach (var itemName in treasureMapPieces)
            {
                itemTotalDropChances.TryAdd(itemName, 0f);
                itemTotalDropChances[itemName] += mapFragmentChance / treasureMapPieces.Count;
            }

            foreach (var kvp in itemTotalDropChances)
            {
                waterFishableRecords.Add(new WaterFishableDBRecord
                {
                    WaterId = waterId,
                    Type = type,
                    ItemName = kvp.Key,
                    DropChance = kvp.Value
                });
            }
        }

        AddFishableRecords(water.DayFishables, "DayFishable");
        AddFishableRecords(water.NightFishables, "NightFishable");

        return waterFishableRecords;
    }
}