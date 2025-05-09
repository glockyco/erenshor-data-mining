#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ItemListener : IAssetScanListener<Item>
{
    private readonly SQLiteConnection _db;
    private readonly List<ItemDBRecord> _records = new();

    public ItemListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<ItemDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ItemDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(Item asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new ItemDBRecord
        {
            // @TODO: Fill fields (see ItemExportStep).
        };

        _records.Add(record);
    }
}