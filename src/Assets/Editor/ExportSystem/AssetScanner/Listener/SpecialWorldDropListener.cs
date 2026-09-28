#nullable enable

using System;
using System.Collections.Generic;
using SQLite;
using UnityEngine;

/// <summary>
/// Exports the item pools and flags of the special world drops that
/// LootTable.InitLootTable rolls on every kill. The pools live on the
/// GameManager and Misc components in LoadScene. The chances and level gates
/// come from code facts, not from here.
///
/// The listener is registered for both component types, so the scanner calls
/// OnScanFinished once per registration. It writes on the first call.
/// </summary>
public class SpecialWorldDropListener : IAssetScanListener<GameManager>, IAssetScanListener<Misc>
{
    private readonly SQLiteConnection _db;
    private readonly List<SpecialWorldDropItemRecord> _items = new();
    private readonly List<SpecialWorldDropFlagRecord> _flags = new();
    private int _gameManagerCount;
    private int _miscCount;
    private bool _written;

    public SpecialWorldDropListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnAssetFound(GameManager manager)
    {
        _gameManagerCount++;
        AddSingle("Sivak", manager.Sivak);
        AddList("WorldDropMolds", manager.WorldDropMolds);
        AddList("Maps", manager.Maps);
        AddSingle("XPPot", manager.XPPot);
        AddSingle("InertDiamond", manager.InertDiamond);
        AddSingle("PlanarShard", manager.PlanarShard);
        AddSingle("CrystallizedBalance", manager.CrystallizedBalance);
        AddSingle("Planar", manager.Planar);
        AddSingle("Empty2", manager.Empty2);
        _flags.Add(
            new SpecialWorldDropFlagRecord { Name = "DropMasks", Value = manager.DropMasks }
        );
        _flags.Add(
            new SpecialWorldDropFlagRecord { Name = "DemoBuild", Value = manager.DemoBuild }
        );
    }

    public void OnAssetFound(Misc misc)
    {
        _miscCount++;
        AddList("Masks", misc.Masks);
        AddSingle("MoloraiMask", misc.MoloraiMask);
        AddSingle("EssenceOfAmarion", misc.EssenceOfAmarion);
    }

    public void OnScanFinished()
    {
        if (_written)
        {
            return;
        }
        _written = true;

        // A moved or duplicated component would silently empty or double the pools.
        if (_gameManagerCount != 1 || _miscCount != 1)
        {
            throw new InvalidOperationException(
                $"Expected exactly one GameManager and one Misc component, found "
                    + $"{_gameManagerCount} GameManager and {_miscCount} Misc"
            );
        }

        _db.CreateTable<SpecialWorldDropItemRecord>();
        _db.CreateTable<SpecialWorldDropFlagRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<SpecialWorldDropItemRecord>();
            _db.DeleteAll<SpecialWorldDropFlagRecord>();
            _db.InsertAll(_items);
            _db.InsertAll(_flags);
        });
        Debug.Log($"[{GetType().Name}] Wrote {_items.Count} pool entries and {_flags.Count} flags");
    }

    private void AddSingle(string pool, Item? item)
    {
        _items.Add(
            new SpecialWorldDropItemRecord
            {
                Pool = pool,
                Position = 0,
                ItemStableKey = item == null ? null : StableKeyGenerator.ForItem(item),
            }
        );
    }

    private void AddList(string pool, List<Item>? items)
    {
        if (items == null)
        {
            throw new InvalidOperationException($"Special world drop pool {pool} is null");
        }
        for (int position = 0; position < items.Count; position++)
        {
            Item item = items[position];
            if (item == null)
            {
                Debug.LogWarning($"[{GetType().Name}] {pool}[{position}] is empty");
            }
            _items.Add(
                new SpecialWorldDropItemRecord
                {
                    Pool = pool,
                    Position = position,
                    ItemStableKey = item == null ? null : StableKeyGenerator.ForItem(item),
                }
            );
        }
    }
}
