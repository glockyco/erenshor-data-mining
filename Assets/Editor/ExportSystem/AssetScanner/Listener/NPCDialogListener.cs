#nullable enable

using System.Collections.Generic;
using UnityEngine;

public class NPCDialogListener : IAssetScanListener<NPCDialog>
{
    public readonly List<NPCDialogDBRecord> Records = new();

    public void OnAssetFound(NPCDialog asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new NPCDialogDBRecord
        {
            // @TODO: Fill fields (see NPCDialogExportStep).
        };

        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}