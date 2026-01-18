using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class TreasureLocListener : IAssetScanListener<TreasureLoc>
{
    private readonly SQLiteConnection _db;
    private readonly List<TreasureLocationRecord> _records = new();

    public TreasureLocListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<TreasureLocationRecord>();

        _db.DeleteAll<TreasureLocationRecord>();
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

    private TreasureLocationRecord CreateRecord(TreasureLoc treasureLoc)
    {
        var scene = treasureLoc.gameObject.scene.name;
        var x = treasureLoc.transform.position.x;
        var y = treasureLoc.transform.position.y;
        var z = treasureLoc.transform.position.z;

        return new TreasureLocationRecord
        {
            StableKey = StableKeyGenerator.ForTreasureLocation(scene, x, y, z),
            Scene = scene,
            X = x,
            Y = y,
            Z = z
        };
    }
}
