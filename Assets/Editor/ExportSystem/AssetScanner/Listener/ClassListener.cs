#nullable enable

using System.Collections.Generic;
using UnityEngine;

public class ClassListener : IAssetScanListener<Class>
{
    public readonly List<ClassDBRecord> Records = new();

    public void OnAssetFound(Class asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new ClassDBRecord
        {
            ClassName = asset.ClassName,
            MitigationBonus = asset.MitigationBonus,
            StrBenefit = asset.StrBenefit,
            EndBenefit = asset.EndBenefit,
            DexBenefit = asset.DexBenefit,
            AgiBenefit = asset.AgiBenefit,
            IntBenefit = asset.IntBenefit,
            WisBenefit = asset.WisBenefit,
            ChaBenefit = asset.ChaBenefit,
            AggroMod = asset.AggroMod,
            ResourceName = asset.name,
        };

        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}