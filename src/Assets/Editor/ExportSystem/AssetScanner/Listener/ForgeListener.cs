using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ForgeListener : IAssetScanListener<ForgeEffect>
{
    private readonly SQLiteConnection _db;
    private readonly List<ForgeRecord> _records = new();

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

        _records.Add(new ForgeRecord
        {
            StableKey = StableKeyGenerator.ForForge(scene, x, y, z),
            Scene = scene,
            X = x,
            Y = y,
            Z = z
        });
    }
}
