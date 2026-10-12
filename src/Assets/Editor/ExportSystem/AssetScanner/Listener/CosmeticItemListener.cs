#nullable enable

using System;
using System.Collections.Generic;
using SQLite;
using UnityEngine;

/// <summary>
/// Exports the items that the player's <c>Inventory</c> names for its cosmetic slot
/// effects. <c>Inventory.Update</c> turns on <c>BeltLamp</c> while a cosmetic slot holds
/// <c>BeltLampItem</c>, <c>ShiveringBeltLamp</c>, or <c>KeepersLamp</c>, and
/// <c>FernallanLensObj</c> while one holds <c>WatchersLens</c>, which also lets
/// Sivakayan spectres appear (<c>ZoneAnnounce.Update</c>). The player's inventory is the
/// only one in LoadScene with <c>isPlayer</c> set.
/// </summary>
public class CosmeticItemListener : IAssetScanListener<Inventory>
{
    private readonly SQLiteConnection _db;
    private readonly List<CosmeticItemRecord> _records = new();
    private int _players;

    public CosmeticItemListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _records.Clear();
        _players = 0;
    }

    public void OnAssetFound(Inventory asset)
    {
        if (asset == null || !asset.isPlayer || string.IsNullOrEmpty(asset.gameObject.scene.name))
        {
            return;
        }
        _players++;
        // code-fact: cosmetics.belt_lamp_items
        Add(asset.BeltLampItem, nameof(Inventory.BeltLampItem), nameof(Inventory.BeltLamp));
        Add(
            asset.ShiveringBeltLamp,
            nameof(Inventory.ShiveringBeltLamp),
            nameof(Inventory.BeltLamp)
        );
        Add(asset.KeepersLamp, nameof(Inventory.KeepersLamp), nameof(Inventory.BeltLamp));
        // code-fact: cosmetics.watchers_lens
        Add(asset.WatchersLens, nameof(Inventory.WatchersLens), nameof(Inventory.FernallanLensObj));
    }

    public void OnScanFinished()
    {
        if (_players != 1)
        {
            throw new InvalidOperationException(
                $"Expected exactly one player Inventory, found {_players}"
            );
        }
        _db.CreateTable<CosmeticItemRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<CosmeticItemRecord>();
            _db.InsertAll(_records);
        });
        Debug.Log($"[{GetType().Name}] Wrote {_records.Count} cosmetic items");
        _records.Clear();
    }

    private void Add(Item? item, string field, string effect)
    {
        if (item == null)
        {
            throw new InvalidOperationException($"The player's Inventory has no {field}");
        }
        _records.Add(
            new CosmeticItemRecord
            {
                ItemStableKey = StableKeyGenerator.ForItem(item),
                Effect = effect,
                Field = field,
            }
        );
    }
}
