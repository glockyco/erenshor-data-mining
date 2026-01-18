using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ForgeListener : IAssetScanListener<ForgeEffect>
{
    private readonly SQLiteConnection _db;
    private readonly List<ForgeRecord> _records = new();
    private readonly DuplicateKeyTracker _keyTracker = new("ForgeListener");

    public ForgeListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<ForgeRecord>();
        _db.DeleteAll<ForgeRecord>();
        _records.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_records);
        _records.Clear();
    }

    public void OnAssetFound(ForgeEffect asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var scene = asset.gameObject.scene.name;
        var x = asset.transform.position.x;
        var y = asset.transform.position.y;
        var z = asset.transform.position.z;

        var baseStableKey = StableKeyGenerator.ForForge(scene, x, y, z);
        var stableKey = _keyTracker.GetUniqueKey(baseStableKey, asset.gameObject.name);

        _records.Add(new ForgeRecord
        {
            StableKey = stableKey,
            Scene = scene,
            X = x,
            Y = y,
            Z = z
        });
    }
}
