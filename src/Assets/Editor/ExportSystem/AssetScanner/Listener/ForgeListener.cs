using System.Collections.Generic;
using SQLite;
using UnityEngine;
using static CoordinateRecord;

public class ForgeListener : IAssetScanListener<ForgeEffect>
{
    private readonly SQLiteConnection _db;
    private readonly List<CoordinateRecord> _records = new();

    public ForgeListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateRecord>();
        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.Forge));
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

        _records.Add(new CoordinateRecord
        {
            Scene = asset.gameObject.scene.name,
            X = asset.transform.position.x,
            Y = asset.transform.position.y,
            Z = asset.transform.position.z,
            Category = nameof(CoordinateCategory.Forge)
        });
    }
}
