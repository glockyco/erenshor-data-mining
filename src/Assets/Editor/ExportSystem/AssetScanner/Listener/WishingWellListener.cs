using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class WishingWellListener : IAssetScanListener<GameObject>
{
    private readonly SQLiteConnection _db;
    private readonly List<WishingWellRecord> _records = new();
    private readonly HashSet<(string scene, float x, float z)> _seenPositions = new();

    public WishingWellListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<WishingWellRecord>();
        _db.DeleteAll<WishingWellRecord>();
        _records.Clear();
        _seenPositions.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_records);
        _records.Clear();
        _seenPositions.Clear();
    }

    public void OnAssetFound(GameObject asset)
    {
        if (!asset.CompareTag("Bind"))
        {
            return;
        }

        var scene = asset.scene.name;
        var x = asset.transform.position.x;
        var y = asset.transform.position.y;
        var z = asset.transform.position.z;
        var key = (scene, x, z);

        if (_seenPositions.Contains(key))
        {
            return;
        }

        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(new WishingWellRecord
        {
            StableKey = StableKeyGenerator.ForWishingWell(scene, x, y, z),
            Scene = scene,
            X = x,
            Y = y,
            Z = z
        });

        _seenPositions.Add(key);
    }
}
