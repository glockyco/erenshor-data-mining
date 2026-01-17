#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ZoneAtlasEntryListener : IAssetScanListener<ZoneAtlasEntry>
{
    private readonly SQLiteConnection _db;
    private readonly List<ZoneAtlasEntryRecord> _records = new();
    private readonly List<ZoneAtlasNeighborRecord> _neighborRecords = new();

    public ZoneAtlasEntryListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<ZoneAtlasEntryRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ZoneAtlasEntryRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();

        _db.CreateTable<ZoneAtlasNeighborRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ZoneAtlasNeighborRecord>();
            _db.InsertAll(_neighborRecords);
        });
        _neighborRecords.Clear();
    }

    public void OnAssetFound(ZoneAtlasEntry asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        ZoneAtlasEntryRecord record = new ZoneAtlasEntryRecord
        {
            AtlasIndex = _records.Count,
            Id = asset.Id,
            ZoneName = asset.ZoneName,
            LevelRangeLow = asset.LevelRangeLow,
            LevelRangeHigh = asset.LevelRangeHigh,
            Dungeon = asset.Dungeon,
            ResourceName = asset.name,
        };

        _records.Add(record);

        if (asset.NeighboringZones != null)
        {
            foreach (var neighborZoneName in asset.NeighboringZones)
            {
                if (!string.IsNullOrEmpty(neighborZoneName))
                {
                    _neighborRecords.Add(new ZoneAtlasNeighborRecord
                    {
                        ZoneAtlasId = asset.Id,
                        NeighborZoneStableKey = StableKeyGenerator.ForZoneFromSceneName(neighborZoneName)
                    });
                }
            }
        }
    }
}
