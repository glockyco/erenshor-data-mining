using System.Collections.Generic;
using UnityEngine;

public class SpawnPointScanListener : IAssetScanListener<SpawnPoint>
{
    public readonly List<SpawnPointDBRecord> Records = new();

    public void OnAssetFound(SpawnPoint asset)
    {
        Debug.Log($"[SpawnPointScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null) return;
        var record = new SpawnPointDBRecord
        {
            // @TODO: Fill fields (see SpawnPointExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}