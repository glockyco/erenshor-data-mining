#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class QuestListener : IAssetScanListener<Quest>
{
    private readonly SQLiteConnection _db;
    private readonly List<QuestDBRecord> _records = new();

    public QuestListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<QuestDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<QuestDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(Quest asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new QuestDBRecord
        {
            // @TODO: Fill fields (see QuestExportStep).
        };

        _records.Add(record);
    }
}