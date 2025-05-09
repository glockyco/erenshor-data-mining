#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class SpellListener : IAssetScanListener<Spell>
{
    private readonly SQLiteConnection _db;
    private readonly List<SpellDBRecord> _records = new();

    public SpellListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<SpellDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<SpellDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(Spell asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new SpellDBRecord
        {
            // @TODO: Fill fields (see SpellExportStep).
        };

        _records.Add(record);
    }
}