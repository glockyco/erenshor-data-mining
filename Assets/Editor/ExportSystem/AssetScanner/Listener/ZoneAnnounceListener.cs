#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ZoneAnnounceListener : IAssetScanListener<ZoneAnnounce>
{
    private readonly SQLiteConnection _db;
    private readonly List<ZoneAnnounceRecord> _records = new();

    public ZoneAnnounceListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<ZoneAnnounceRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ZoneAnnounceRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(ZoneAnnounce asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        ZoneAnnounceRecord record = new ZoneAnnounceRecord
        {
            SceneName = asset.gameObject.scene.name,
            ZoneName = asset.ZoneName,
            IsDungeon = asset.isDungeon,
            Achievement = asset.Achievement,
            CompleteQuestOnEnter = asset.CompleteQuestOnEnter,
            CompleteSecondQuestOnEnter = asset.CompleteSecondQuestOnEnter,
            AssignQuestOnEnter = asset.AssignQuestOnEnter
        };

        _records.Add(record);
    }
}