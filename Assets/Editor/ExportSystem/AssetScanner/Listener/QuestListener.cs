#nullable enable

using System.Collections.Generic;
using UnityEngine;

public class QuestListener : IAssetScanListener<Quest>
{
    public readonly List<QuestDBRecord> Records = new();

    public void OnAssetFound(Quest asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new QuestDBRecord
        {
            // @TODO: Fill fields (see QuestExportStep).
        };

        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}