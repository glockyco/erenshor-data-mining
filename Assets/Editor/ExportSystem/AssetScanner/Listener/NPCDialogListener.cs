#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class NPCDialogListener : IAssetScanListener<NPCDialog>
{
    private readonly SQLiteConnection _db;
    private readonly List<NPCDialogDBRecord> _records = new();

    public NPCDialogListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<NPCDialogDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<NPCDialogDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(NPCDialog asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new NPCDialogDBRecord
        {
            // @TODO: Fill fields (see NPCDialogExportStep).
        };

        _records.Add(record);
    }
}