#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class WorldFactionListener : IAssetScanListener<WorldFaction>
{
    private readonly SQLiteConnection _db;
    private readonly List<WorldFactionDBRecord> _records = new();

    public WorldFactionListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<WorldFactionDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<WorldFactionDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(WorldFaction asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new WorldFactionDBRecord
        {
            REFNAME = asset.REFNAME,
            FactionDBIndex = _records.Count,
            FactionName = asset.FactionName,
            FactionDesc = asset.FactionDesc,
            DefaultValue = asset.DEFAULTVAL,
            ResourceName = asset.name,
        };

        _records.Add(record);
    }
}