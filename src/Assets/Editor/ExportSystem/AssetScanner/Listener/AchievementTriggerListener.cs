using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class AchievementTriggerListener : IAssetScanListener<AchievementTrigger>
{
    private readonly SQLiteConnection _db;
    private readonly List<AchievementTriggerRecord> _records = new();
    private readonly DuplicateKeyTracker _keyTracker = new("AchievementTriggerListener");

    public AchievementTriggerListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<AchievementTriggerRecord>();

        _db.DeleteAll<AchievementTriggerRecord>();

        _records.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_records);
        _records.Clear();
    }

    public void OnAssetFound(AchievementTrigger asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset));
    }

    private AchievementTriggerRecord CreateRecord(AchievementTrigger achievementTrigger)
    {
        var scene = achievementTrigger.gameObject.scene.name;
        var x = achievementTrigger.transform.position.x;
        var y = achievementTrigger.transform.position.y;
        var z = achievementTrigger.transform.position.z;

        var baseStableKey = StableKeyGenerator.ForAchievementTrigger(scene, x, y, z);
        var stableKey = _keyTracker.GetUniqueKey(baseStableKey, achievementTrigger.gameObject.name);

        return new AchievementTriggerRecord
        {
            StableKey = stableKey,
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            AchievementName = achievementTrigger.AchievementName
        };
    }
}
