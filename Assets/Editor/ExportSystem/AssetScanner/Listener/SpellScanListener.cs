using System.Collections.Generic;
using UnityEngine;

public class SpellScanListener : IAssetScanListener<Spell>
{
    public readonly List<SpellDBRecord> Records = new();

    public void OnAssetFound(Spell asset)
    {
        Debug.Log($"[SpellScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null) return;
        var record = new SpellDBRecord
        {
            // @TODO: Fill fields (see SpellExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}