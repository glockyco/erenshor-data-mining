#nullable enable

using System.Collections.Generic;
using UnityEngine;

public class SpawnPointListener : IAssetScanListener<SpawnPoint>
{
    public readonly List<SpawnPointDBRecord> Records = new();

    public void OnAssetFound(SpawnPoint asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new SpawnPointDBRecord
        {
            // @TODO: Fill fields (see SpawnPointExportStep).
        };

        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}