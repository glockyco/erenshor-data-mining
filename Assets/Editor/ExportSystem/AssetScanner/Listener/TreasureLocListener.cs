using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class TreasureLocListener : IAssetScanListener<TreasureLoc>
{
    private readonly SQLiteConnection _db;
    private readonly List<TreasureLocDBRecord> _records = new();
    private readonly Dictionary<string, int> _recordCounts = new();

    public TreasureLocListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<TreasureLocDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<TreasureLocDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
        _recordCounts.Clear();
    }

    public void OnAssetFound(TreasureLoc asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset));
    }

    private TreasureLocDBRecord CreateRecord(TreasureLoc treasureLoc)
    {
        var baseId = treasureLoc.gameObject.scene.name + treasureLoc.transform.position;
        var spawnPointIndex = _recordCounts.GetValueOrDefault(baseId, 0);
        _recordCounts[baseId] = spawnPointIndex + 1;
        var finalId = baseId + (spawnPointIndex > 0 ? $"_{spawnPointIndex + 1}" : "");
        
        return new TreasureLocDBRecord
        {
            Id = finalId,
            SceneName = treasureLoc.gameObject.scene.name,
            PositionX = treasureLoc.transform.position.x,
            PositionY = treasureLoc.transform.position.y,
            PositionZ = treasureLoc.transform.position.z,
        };
    }
}