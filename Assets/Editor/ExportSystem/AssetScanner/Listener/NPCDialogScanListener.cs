using System.Collections.Generic;
using UnityEngine;

public class NPCDialogScanListener : IAssetScanListener<NPCDialog>
{
    public readonly List<NPCDialogDBRecord> Records = new();

    public void OnAssetFound(NPCDialog asset)
    {
        Debug.Log($"[NPCDialogScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null) return;
        var record = new NPCDialogDBRecord
        {
            // @TODO: Fill fields (see NPCDialogExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}