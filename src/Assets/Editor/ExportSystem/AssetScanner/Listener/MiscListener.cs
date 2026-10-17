#nullable enable

using System;
using System.Collections.Generic;
using SQLite;
using UnityEngine;

/// <summary>
/// Captures the native fossil pool and aggregates its outcomes for every click-item source.
/// Only stable keys survive scene unload. Items and Spells must finish before this listener.
/// </summary>
public class MiscListener : IAssetScanListener<Misc>
{
    // code-fact: item.fossil_pool_grant
    private const string FossilPoolKey = "Misc.FossilGame";
    private readonly SQLiteConnection _db;
    private readonly List<ItemDropPoolSlotRecord> _slots = new();
    private ItemDropPoolRecord? _pool;

    public MiscListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnAssetFound(Misc asset)
    {
        if (_pool != null)
            throw new InvalidOperationException(
                "Expected exactly one Misc component for Misc.FossilGame"
            );
        if (asset.FossilGame == null || asset.FossilGame.Count == 0)
            throw new InvalidOperationException(
                "Misc.FossilGame is null or empty and cannot supply a native pool roll"
            );

        _pool = new ItemDropPoolRecord
        {
            PoolStableKey = FossilPoolKey,
            SourceComponentKey =
                ActivationTargetResolver.ObjectKey(asset.gameObject) + ":script:Misc:0",
            SlotCount = asset.FossilGame.Count,
        };
        for (int position = 0; position < asset.FossilGame.Count; position++)
        {
            var item = asset.FossilGame[position];
            _slots.Add(
                new ItemDropPoolSlotRecord
                {
                    PoolStableKey = FossilPoolKey,
                    Position = position,
                    ItemStableKey = item != null ? StableKeyGenerator.ForItem(item) : null,
                }
            );
        }
    }

    public void OnScanFinished()
    {
        var pool =
            _pool
            ?? throw new InvalidOperationException(
                "Expected exactly one Misc component for Misc.FossilGame, found none"
            );
        // SpellName is the native SpellVessel switch discriminator, not an entity-name join.
        var sources = _db.Query<ItemStableKeyResult>(
            @"SELECT i.StableKey
              FROM Items i
              JOIN Spells s ON s.StableKey = i.ItemEffectOnClickStableKey
              WHERE s.SpellName = ?
              ORDER BY i.StableKey",
            "Break Fossil"
        );
        if (sources.Count == 0)
            throw new InvalidOperationException(
                "No exported item clicks a spell with SpellName 'Break Fossil'"
            );

        var counts = new Dictionary<string, int>();
        foreach (var slot in _slots)
        {
            if (slot.ItemStableKey == null)
                continue;
            if (!counts.ContainsKey(slot.ItemStableKey))
            {
                // A referenced item missing from the export is not an empty native slot.
                _db.Get<ItemRecord>(slot.ItemStableKey);
                counts[slot.ItemStableKey] = 0;
            }
            counts[slot.ItemStableKey]++;
        }

        var records = new List<ItemDropRecord>();
        foreach (var source in sources)
        {
            foreach (var outcome in counts)
            {
                records.Add(
                    new ItemDropRecord
                    {
                        PoolStableKey = pool.PoolStableKey,
                        SourceItemStableKey = source.StableKey,
                        DroppedItemStableKey = outcome.Key,
                        DropProbability = (double)outcome.Value / pool.SlotCount * 100.0,
                        IsGuaranteed = true, // The native operation performs one pool roll.
                    }
                );
            }
        }

        _db.CreateTable<ItemDropPoolRecord>();
        _db.CreateTable<ItemDropPoolSlotRecord>();
        _db.CreateTable<ItemDropRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ItemDropRecord>();
            _db.DeleteAll<ItemDropPoolSlotRecord>();
            _db.DeleteAll<ItemDropPoolRecord>();
            _db.Insert(pool);
            _db.InsertAll(_slots);
            _db.InsertAll(records);
        });

        Debug.Log(
            $"[{GetType().Name}] Wrote {_slots.Count} native pool slots and {records.Count} item drop outcomes for {sources.Count} source items"
        );
        _slots.Clear();
        _pool = null;
    }

    private sealed class ItemStableKeyResult
    {
        public string StableKey { get; set; } = string.Empty;
    }
}
