using System.Collections.Generic;
using UnityEngine;

public class ItemScanListener : IAssetScanListener<Item>
{
    public readonly List<ItemDBRecord> Records = new();

    public void OnAssetFound(Item asset)
    {
        Debug.Log($"[ItemScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null || string.IsNullOrEmpty(asset.Id)) return;
        var record = new ItemDBRecord
        {
            // @TODO: Fill fields (see ItemExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}