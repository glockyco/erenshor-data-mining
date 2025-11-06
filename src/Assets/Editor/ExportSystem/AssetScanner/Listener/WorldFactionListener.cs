#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class WorldFactionListener : IAssetScanListener<WorldFaction>
{
    private readonly SQLiteConnection _db;
    private readonly List<WorldFactionRecord> _records = new();

    public WorldFactionListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<WorldFactionRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<WorldFactionRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(WorldFaction asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new WorldFactionRecord
        {
            StableKey = StableKeyGenerator.ForFaction(asset),
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