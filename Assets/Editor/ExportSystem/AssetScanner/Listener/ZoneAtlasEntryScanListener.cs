using System.Collections.Generic;
using UnityEngine;

public class ZoneAtlasEntryScanListener : IAssetScanListener<ZoneAtlasEntry>
{
    public readonly List<ZoneAtlasEntryDBRecord> Records = new();

    public void OnAssetFound(ZoneAtlasEntry asset)
    {
        Debug.Log($"[ZoneAtlasEntryScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null) return;
        var record = new ZoneAtlasEntryDBRecord
        {
            // @TODO: Fill fields (see ZoneAtlasExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}