#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class CharacterListener : IAssetScanListener<Character>
{
    private readonly SQLiteConnection _db;
    private readonly List<CharacterDBRecord> _records = new();

    public CharacterListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<CharacterDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<CharacterDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(Character asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new CharacterDBRecord
        {
            // @TODO: Fill fields (see CharacterExportStep).
        };

        _records.Add(record);
    }
}