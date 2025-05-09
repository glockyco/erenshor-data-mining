#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ZoneAtlasEntryListener : IAssetScanListener<ZoneAtlasEntry>
{
    private readonly SQLiteConnection _db;
    private readonly List<ZoneAtlasEntryDBRecord> _records = new();

    public ZoneAtlasEntryListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<ZoneAtlasEntryDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ZoneAtlasEntryDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(ZoneAtlasEntry asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        string neighboringZones = string.Join(", ", asset!.NeighboringZones ?? new List<string>());

        ZoneAtlasEntryDBRecord record = new ZoneAtlasEntryDBRecord
        {
            AtlasIndex = _records.Count,
            Id = asset.Id,
            ZoneName = asset.ZoneName,
            LevelRangeLow = asset.LevelRangeLow,
            LevelRangeHigh = asset.LevelRangeHigh,
            Dungeon = asset.Dungeon,
            NeighboringZones = neighboringZones,
            ResourceName = asset.name,
        };

        _records.Add(record);
    }
}