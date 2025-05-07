using System.Collections.Generic;
using UnityEngine;

public class WorldFactionScanListener : IAssetScanListener<WorldFaction>
{
    public readonly List<WorldFactionDBRecord> Records = new();

    public void OnAssetFound(WorldFaction asset)
    {
        Debug.Log($"[FactionScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null) return;
        var record = new WorldFactionDBRecord
        {
            // @TODO: Fill fields (see FactionExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}