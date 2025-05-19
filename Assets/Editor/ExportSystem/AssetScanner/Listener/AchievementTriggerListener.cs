using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class AchievementTriggerListener : IAssetScanListener<AchievementTrigger>
{
    private readonly SQLiteConnection _db;
    private readonly List<AchievementTriggerDBRecord> _records = new();
    private readonly Dictionary<string, int> _recordCounts = new();

    public AchievementTriggerListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<AchievementTriggerDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<AchievementTriggerDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
        _recordCounts.Clear();
    }

    public void OnAssetFound(AchievementTrigger asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset));
    }

    private AchievementTriggerDBRecord CreateRecord(AchievementTrigger achievementTrigger)
    {
        var baseId = achievementTrigger.gameObject.scene.name + achievementTrigger.transform.position;
        var spawnPointIndex = _recordCounts.GetValueOrDefault(baseId, 0);
        _recordCounts[baseId] = spawnPointIndex + 1;
        var finalId = baseId + (spawnPointIndex > 0 ? $"_{spawnPointIndex + 1}" : "");

        return new AchievementTriggerDBRecord
        {
            Id = finalId,
            SceneName = achievementTrigger.gameObject.scene.name,
            PositionX = achievementTrigger.transform.position.x,
            PositionY = achievementTrigger.transform.position.y,
            PositionZ = achievementTrigger.transform.position.z,
            AchievementName = achievementTrigger.AchievementName
        };
    }
}