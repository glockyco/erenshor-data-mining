#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class SpawnPointListener : IAssetScanListener<SpawnPoint>
{
    private readonly SQLiteConnection _db;
    private readonly List<SpawnPointDBRecord> _records = new();

    public SpawnPointListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<SpawnPointDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<SpawnPointDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(SpawnPoint asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new SpawnPointDBRecord
        {
            // @TODO: Fill fields (see SpawnPointExportStep).
        };

        _records.Add(record);
    }
}