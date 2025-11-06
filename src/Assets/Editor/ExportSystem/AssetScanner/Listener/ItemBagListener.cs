#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;
using static CoordinateRecord;

public class ItemBagListener : IAssetScanListener<ItemBag>
{
    private readonly SQLiteConnection _db;
    private readonly List<CoordinateRecord> _coordinateRecords = new();
    private readonly List<ItemBagRecord> _itemBagRecords = new();

    public ItemBagListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateRecord>();
        _db.CreateTable<ItemBagRecord>();

        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.ItemBag));
        _db.DeleteAll<ItemBagRecord>();

        _coordinateRecords.Clear();
        _itemBagRecords.Clear();
    }

    public void OnScanFinished()
    {
        _db.RunInTransaction(() =>
        {
            _db.InsertAll(_coordinateRecords);
            _db.InsertAll(_itemBagRecords);
        });

        _db.Execute(@"
            UPDATE Coordinates
            SET ItemBagId = (
                SELECT Id
                FROM ItemBags
                WHERE ItemBags.CoordinateId = Coordinates.Id
            )
            WHERE EXISTS (
                SELECT 1
                FROM ItemBags
                WHERE ItemBags.CoordinateId = Coordinates.Id
            );
        ");

        _coordinateRecords.Clear();
        _itemBagRecords.Clear();
    }

    public void OnAssetFound(ItemBag asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var coordinate = new CoordinateRecord
        {
            Scene = asset.gameObject.scene.name,
            X = asset.transform.position.x,
            Y = asset.transform.position.y,
            Z = asset.transform.position.z,
            Category = nameof(CoordinateCategory.ItemBag)
        };

        var itemBag = new ItemBagRecord
        {
            Id = TableIdGenerator.NextId(ItemBagRecord.TableName),
            CoordinateId = coordinate.Id,
            ItemStableKey = asset.Contents != null
                ? StableKeyGenerator.ForItem(asset.Contents)
                : null,
            Respawns = asset.Respawns,
            RespawnTimer = asset.RespawnTimer
        };

        coordinate.ItemBagId = itemBag.Id;

        _coordinateRecords.Add(coordinate);
        _itemBagRecords.Add(itemBag);
    }
}