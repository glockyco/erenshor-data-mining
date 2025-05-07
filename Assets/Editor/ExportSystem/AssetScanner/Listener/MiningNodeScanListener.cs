using System.Collections.Generic;
using UnityEngine;

public class MiningNodeScanListener : IAssetScanListener<MiningNode>
{
    public readonly List<MiningNodeDBRecord> Records = new();

    public void OnAssetFound(MiningNode asset)
    {
        Debug.Log($"[MiningNodeScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null) return;
        var record = new MiningNodeDBRecord
        {
            // @TODO: Fill fields (see MiningNodeExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}