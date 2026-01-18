using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class WishingWellListener : IAssetScanListener<GameObject>
{
    private readonly SQLiteConnection _db;
    private readonly List<WishingWellRecord> _records = new();
    private readonly DuplicateKeyTracker _keyTracker = new("WishingWellListener");

    public WishingWellListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<WishingWellRecord>();
        _db.DeleteAll<WishingWellRecord>();
        _records.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_records);
        _records.Clear();
    }

    public void OnAssetFound(GameObject asset)
    {
        if (!asset.CompareTag("Bind"))
        {
            return;
        }

        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var scene = asset.scene.name;
        var x = asset.transform.position.x;
        var y = asset.transform.position.y;
        var z = asset.transform.position.z;

        var baseStableKey = StableKeyGenerator.ForWishingWell(scene, x, y, z);
        var stableKey = _keyTracker.GetUniqueKey(baseStableKey, asset.name);

        _records.Add(new WishingWellRecord
        {
            StableKey = stableKey,
            Scene = scene,
            X = x,
            Y = y,
            Z = z
        });
    }
}
