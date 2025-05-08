#nullable enable

using System.Collections.Generic;
using UnityEngine;

public class LootTableListener : IAssetScanListener<LootTable>
{
    public readonly List<LootTableDBRecord> Records = new();

    public void OnAssetFound(LootTable asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new LootTableDBRecord
        {
            // @TODO: Fill fields (see LootDropExportStep).
        };

        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}