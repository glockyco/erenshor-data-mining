using System.Collections.Generic;
using SQLite;
using UnityEngine;
using static CoordinateDBRecord;

public class WishingWellListener : IAssetScanListener<GameObject>
{
    private readonly SQLiteConnection _db;
    private readonly List<CoordinateDBRecord> _records = new();
    private readonly HashSet<(string scene, float x, float z)> _seenPositions = new();

    public WishingWellListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateDBRecord>();
        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.WishingWell));
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

        _records.Add(new CoordinateDBRecord
        {
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            Category = nameof(CoordinateCategory.WishingWell)
        });

        _seenPositions.Add(key);
    }
}