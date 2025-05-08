using System.Collections.Generic;
using UnityEngine;

public class AscensionListener : IAssetScanListener<Ascension>
{
    public readonly List<AscensionDBRecord> Records = new();

    public void OnAssetFound(Ascension asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null) return;
        var record = new AscensionDBRecord
        {
            // @TODO: Fill fields (see AscensionExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}