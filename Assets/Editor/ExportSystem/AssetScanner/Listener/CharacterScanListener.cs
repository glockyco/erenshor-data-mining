using System.Collections.Generic;
using UnityEngine;

public class CharacterScanListener : IAssetScanListener<Character>
{
    public readonly List<CharacterDBRecord> Records = new();

    public void OnAssetFound(Character asset)
    {
        Debug.Log($"[CharacterScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null) return;
        var record = new CharacterDBRecord
        {
            // @TODO: Fill fields (see CharacterExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}