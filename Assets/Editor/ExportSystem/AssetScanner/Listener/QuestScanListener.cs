using System.Collections.Generic;
using UnityEngine;

public class QuestScanListener : IAssetScanListener<Quest>
{
    public readonly List<QuestDBRecord> Records = new();

    public void OnAssetFound(Quest asset)
    {
        Debug.Log($"[QuestScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null) return;
        var record = new QuestDBRecord
        {
            // @TODO: Fill fields (see QuestExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}