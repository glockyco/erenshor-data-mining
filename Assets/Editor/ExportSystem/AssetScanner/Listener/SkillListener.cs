#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class SkillListener : IAssetScanListener<Skill>
{
    private readonly SQLiteConnection _db;
    private readonly List<SkillDBRecord> _records = new();

    public SkillListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<SkillDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<SkillDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(Skill asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var record = new SkillDBRecord
        {
            // @TODO: Fill fields (see SkillExportStep).
        };

        _records.Add(record);
    }
}