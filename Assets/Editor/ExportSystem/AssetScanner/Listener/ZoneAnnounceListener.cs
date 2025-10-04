#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ZoneAnnounceListener : IAssetScanListener<ZoneAnnounce>
{
    private readonly SQLiteConnection _db;
    private readonly List<ZoneAnnounceRecord> _records = new();
    private readonly List<QuestZoneAssignmentRecord> _questZoneAssignmentRecords = new();
    private readonly List<QuestZoneCompletionRecord> _questZoneCompletionRecords = new();

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

        // Create and insert junction table records after parent records are inserted
        _db.CreateTable<QuestZoneAssignmentRecord>();
        _db.CreateTable<QuestZoneCompletionRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<QuestZoneAssignmentRecord>();
            _db.DeleteAll<QuestZoneCompletionRecord>();
            _db.InsertAll(_questZoneAssignmentRecords);
            _db.InsertAll(_questZoneCompletionRecords);
        });
        _questZoneAssignmentRecords.Clear();
        _questZoneCompletionRecords.Clear();
    }

    public void OnAssetFound(ZoneAnnounce asset)
    {
        var sceneName = asset.gameObject.scene.name;

        ZoneAnnounceRecord record = new ZoneAnnounceRecord
        {
            SceneName = sceneName,
            ZoneName = asset.ZoneName,
            IsDungeon = asset.isDungeon,
            Achievement = asset.Achievement,
            CompleteQuestOnEnter = asset.CompleteQuestOnEnter,
            CompleteSecondQuestOnEnter = asset.CompleteSecondQuestOnEnter,
            AssignQuestOnEnter = asset.AssignQuestOnEnter
        };

        _records.Add(record);

        // Extract quest zone assignments
        if (!string.IsNullOrEmpty(asset.AssignQuestOnEnter))
        {
            _questZoneAssignmentRecords.Add(new QuestZoneAssignmentRecord
            {
                QuestDBName = asset.AssignQuestOnEnter,
                ZoneSceneName = sceneName
            });
        }

        // Extract quest zone completions
        if (!string.IsNullOrEmpty(asset.CompleteQuestOnEnter))
        {
            _questZoneCompletionRecords.Add(new QuestZoneCompletionRecord
            {
                QuestDBName = asset.CompleteQuestOnEnter,
                ZoneSceneName = sceneName
            });
        }

        if (!string.IsNullOrEmpty(asset.CompleteSecondQuestOnEnter))
        {
            _questZoneCompletionRecords.Add(new QuestZoneCompletionRecord
            {
                QuestDBName = asset.CompleteSecondQuestOnEnter,
                ZoneSceneName = sceneName
            });
        }
    }
}