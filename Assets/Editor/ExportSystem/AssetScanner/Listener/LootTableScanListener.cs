using System.Collections.Generic;
using UnityEngine;

public class LootTableScanListener : IAssetScanListener<LootTable>
{
    public readonly List<LootTableDBRecord> Records = new();

    public void OnAssetFound(LootTable asset)
    {
        Debug.Log($"[LootDropScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null) return;
        var record = new LootTableDBRecord
        {
            // @TODO: Fill fields (see LootDropExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}