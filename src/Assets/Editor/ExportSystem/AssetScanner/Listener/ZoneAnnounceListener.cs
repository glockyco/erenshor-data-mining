#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ZoneAnnounceListener : IAssetScanListener<ZoneAnnounce>
{
    private readonly SQLiteConnection _db;
    private readonly List<ZoneRecord> _records = new();

    public ZoneAnnounceListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<ZoneRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ZoneRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(ZoneAnnounce asset)
    {
        var sceneName = asset.gameObject.scene.name;

        ZoneRecord record = new ZoneRecord
        {
            StableKey = StableKeyGenerator.ForZone(sceneName),
            SceneName = sceneName,
            ZoneName = asset.ZoneName,
            IsDungeon = asset.isDungeon,
            Achievement = asset.Achievement,
            CompleteQuestOnEnterStableKey = !string.IsNullOrEmpty(asset.CompleteQuestOnEnter)
                ? StableKeyGenerator.ForQuestFromDBName(asset.CompleteQuestOnEnter)
                : null,
            CompleteSecondQuestOnEnterStableKey = !string.IsNullOrEmpty(asset.CompleteSecondQuestOnEnter)
                ? StableKeyGenerator.ForQuestFromDBName(asset.CompleteSecondQuestOnEnter)
                : null,
            AssignQuestOnEnterStableKey = !string.IsNullOrEmpty(asset.AssignQuestOnEnter)
                ? StableKeyGenerator.ForQuestFromDBName(asset.AssignQuestOnEnter)
                : null,
            // North bearing from ZoneAnnounce GameObject's Y rotation
            NorthBearing = asset.transform.eulerAngles.y
        };

        _records.Add(record);
    }
}
