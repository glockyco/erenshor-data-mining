using System.Collections.Generic;
using UnityEngine;

public class SkillListener : IAssetScanListener<Skill>
{
    public readonly List<SkillDBRecord> Records = new();

    public void OnAssetFound(Skill asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null) return;
        var record = new SkillDBRecord
        {
            // @TODO: Fill fields (see SkillExportStep).
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}