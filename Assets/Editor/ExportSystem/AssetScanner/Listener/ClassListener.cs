using System.Collections.Generic;
using UnityEngine;

public class ClassListener : IAssetScanListener<Class>
{
    public readonly List<ClassDBRecord> Records = new();

    public void OnAssetFound(Class asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null || string.IsNullOrEmpty(asset.ClassName)) return;
        var record = new ClassDBRecord
        {
            // @TODO: Fill fields (see ClassExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}