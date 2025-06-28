using System.Collections.Generic;
using SQLite;
using UnityEngine;
using static CoordinateDBRecord;

public class WishingWellListener : IAssetScanListener<GameObject>
{
    private readonly SQLiteConnection _db;
    private readonly List<CoordinateDBRecord> _records = new();

    public WishingWellListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateDBRecord>();
        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.WishingWell));
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

        _records.Add(new CoordinateDBRecord
        {
            Scene = asset.scene.name,
            X = asset.transform.position.x,
            Y = asset.transform.position.y,
            Z = asset.transform.position.z,
            Category = nameof(CoordinateCategory.WishingWell)
        });
    }
}