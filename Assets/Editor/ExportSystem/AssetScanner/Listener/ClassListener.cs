#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ClassListener : IAssetScanListener<Class>
{
    private readonly SQLiteConnection _db;
    private readonly List<ClassRecord> _records = new();

    public ClassListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<ClassRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ClassRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(Class asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new ClassRecord
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

        _records.Add(record);
    }
}