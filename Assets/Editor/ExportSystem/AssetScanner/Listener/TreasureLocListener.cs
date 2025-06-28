using System.Collections.Generic;
using SQLite;
using UnityEngine;
using static CoordinateRecord;

public class TreasureLocListener : IAssetScanListener<TreasureLoc>
{
    private readonly SQLiteConnection _db;
    private readonly List<CoordinateRecord> _records = new();

    public TreasureLocListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateRecord>();
        
        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.TreasureLoc));
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_records);
        
        _records.Clear();
    }

    public void OnAssetFound(TreasureLoc asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset));
    }

    private CoordinateRecord CreateRecord(TreasureLoc treasureLoc)
    {
        return new CoordinateRecord
        {
            Scene = treasureLoc.gameObject.scene.name,
            X = treasureLoc.transform.position.x,
            Y = treasureLoc.transform.position.y,
            Z = treasureLoc.transform.position.z,
            Category = nameof(CoordinateCategory.TreasureLoc)
        };
    }
}