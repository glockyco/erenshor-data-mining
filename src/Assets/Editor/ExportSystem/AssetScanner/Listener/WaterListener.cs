#nullable enable

using System;
using System.Collections.Generic;
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

        // A water's local scale ignores its parents' scale and rotation, so the
        // footprint comes from the world-space bounds of what fishing hits.
        var collider = asset.GetComponent<Collider>();
        var renderer = asset.GetComponent<Renderer>();
        Bounds bounds;
        if (collider != null)
        {
            bounds = collider.bounds;
        }
        else if (renderer != null)
        {
            bounds = renderer.bounds;
        }
        else
        {
            throw new InvalidOperationException(
                $"Water {asset.name} in {scene} has neither a collider nor a renderer to size it"
            );
        }

        var water = new WaterRecord
        {
            StableKey = stableKey,
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            Width = bounds.size.x,
            Height = bounds.size.y,
            Depth = bounds.size.z,
        };

        _waterRecords.Add(water);
        _waterFishableRecords.AddRange(CreateWaterFishableRecords(asset, stableKey));
    }

    private static List<WaterFishableRecord> CreateWaterFishableRecords(
        Water water,
        string waterStableKey
    )
    {
        var waterFishableRecords = new List<WaterFishableRecord>();

        void AddFishableRecords(List<Item> fishables, string type)
        {
            for (var position = 0; position < fishables.Count; position++)
            {
                var item = fishables[position];
                waterFishableRecords.Add(
                    new WaterFishableRecord
                    {
                        WaterStableKey = waterStableKey,
                        Type = type,
                        Position = position,
                        ItemStableKey = item != null ? StableKeyGenerator.ForItem(item) : null,
                    }
                );
            }
        }

        AddFishableRecords(water.DayFishables, "DayFishable");
        AddFishableRecords(water.NightFishables, "NightFishable");

        return waterFishableRecords;
    }
}
