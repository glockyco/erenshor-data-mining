#nullable enable

using System.Collections.Generic;
using UnityEngine;

public class SpellListener : IAssetScanListener<Spell>
{
    public readonly List<SpellDBRecord> Records = new();

    public void OnAssetFound(Spell asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new SpellDBRecord
        {
            // @TODO: Fill fields (see SpellExportStep).
        };

        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}