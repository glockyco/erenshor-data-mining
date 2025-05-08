using System.Collections.Generic;
using UnityEngine;

public class ZoneAtlasEntryScanListener : IAssetScanListener<ZoneAtlasEntry>
{
    public readonly List<ZoneAtlasEntryDBRecord> Records = new();

    public void OnAssetFound(ZoneAtlasEntry asset)
    {
        Debug.Log($"[ZoneAtlasEntryScanListener] Found: {asset?.name} ({asset?.GetType().Name})");

        string neighboringZones = string.Join(", ", asset!.NeighboringZones ?? new List<string>());

        ZoneAtlasEntryDBRecord record = new ZoneAtlasEntryDBRecord
        {
            AtlasIndex = Records.Count,
            Id = asset.Id,
            ZoneName = asset.ZoneName,
            LevelRangeLow = asset.LevelRangeLow,
            LevelRangeHigh = asset.LevelRangeHigh,
            Dungeon = asset.Dungeon,
            NeighboringZones = neighboringZones,
            ResourceName = asset.name,
        };

        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}
