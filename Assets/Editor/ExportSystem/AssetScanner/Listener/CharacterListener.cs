#nullable enable

using System.Collections.Generic;
using UnityEngine;

public class CharacterListener : IAssetScanListener<Character>
{
    public readonly List<CharacterDBRecord> Records = new();

    public void OnAssetFound(Character asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new CharacterDBRecord
        {
            // @TODO: Fill fields (see CharacterExportStep).
        };

        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}