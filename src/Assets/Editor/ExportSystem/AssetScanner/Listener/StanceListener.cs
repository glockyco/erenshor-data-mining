#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class StanceListener : IAssetScanListener<Stance>
{
    private readonly SQLiteConnection _db;
    private readonly List<StanceRecord> _records = new();

    public StanceListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<StanceRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<StanceRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(Stance asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new StanceRecord
        {
            StableKey = StableKeyGenerator.ForStance(asset),
            StanceDBIndex = _records.Count,
            Id = asset.Id,
            DisplayName = asset.DisplayName,

            // Stat Modifiers
            MaxHPMod = asset.MaxHPMod,
            DamageMod = asset.DamageMod,
            ProcRateMod = asset.ProcRateMod,
            DamageTakenMod = asset.DamageTakenMod,
            SelfDamagePerAttack = asset.SelfDamagePerAttack,
            AggroGenMod = asset.AggroGenMod,
            SpellDamageMod = asset.SpellDamageMod,
            SelfDamagePerCast = asset.SelfDamagePerCast,
            LifestealAmount = asset.LifestealAmount,
            ResonanceAmount = asset.ResonanceAmount,
            StopRegen = asset.StopRegen,

            // Text
            SwitchMessage = asset.SwitchMessage,
            StanceDesc = asset.StanceDesc,

            ResourceName = asset.name
        };

        _records.Add(record);
    }
}
