#nullable enable

using System.Collections.Generic;
using UnityEngine;

public class WorldFactionListener : IAssetScanListener<WorldFaction>
{
    public readonly List<WorldFactionDBRecord> Records = new();

    public void OnAssetFound(WorldFaction asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new WorldFactionDBRecord
        {
            // @TODO: Fill fields (see FactionExportStep).
        };

        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}