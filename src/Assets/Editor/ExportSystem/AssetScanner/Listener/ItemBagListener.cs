#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ItemBagListener : IAssetScanListener<ItemBag>
{
    private readonly SQLiteConnection _db;
    private readonly List<ItemBagRecord> _itemBagRecords = new();
    private readonly DuplicateKeyTracker _keyTracker = new("ItemBagListener");

    public ItemBagListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<ItemBagRecord>();

        _db.DeleteAll<ItemBagRecord>();

        _itemBagRecords.Clear();
    }

    public void OnScanFinished()
    {
        _db.RunInTransaction(() =>
        {
            _db.InsertAll(_itemBagRecords);
        });

        _itemBagRecords.Clear();
    }

    public void OnAssetFound(ItemBag asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var scene = asset.gameObject.scene.name;
        var x = asset.transform.position.x;
        var y = asset.transform.position.y;
        var z = asset.transform.position.z;

        var baseStableKey = StableKeyGenerator.ForItemBag(scene, x, y, z);
        var stableKey = _keyTracker.GetUniqueKey(baseStableKey, asset.gameObject.name);

        var itemBag = new ItemBagRecord
        {
            StableKey = stableKey,
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            ItemStableKey = asset.Contents != null
                ? StableKeyGenerator.ForItem(asset.Contents)
                : null,
            Respawns = asset.Respawns,
            RespawnTimer = asset.RespawnTimer
        };

        _itemBagRecords.Add(itemBag);
    }
}
