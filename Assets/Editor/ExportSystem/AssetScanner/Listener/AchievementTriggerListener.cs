using System.Collections.Generic;
using SQLite;
using UnityEngine;
using static CoordinateDBRecord;

public class AchievementTriggerListener : IAssetScanListener<AchievementTrigger>
{
    private readonly SQLiteConnection _db;
    private readonly List<AchievementTriggerDBRecord> _records = new();

    public AchievementTriggerListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateDBRecord>();
        _db.CreateTable<AchievementTriggerDBRecord>();

        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.AchievementTrigger));
        _db.DeleteAll<AchievementTriggerDBRecord>();

        _records.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_records);

        _db.Execute(@"
            UPDATE Coordinates
            SET AchievementTriggerId = (
                SELECT Id
                FROM AchievementTriggers
                WHERE AchievementTriggers.CoordinateId = Coordinates.Id
            )
            WHERE EXISTS (
                SELECT 1
                FROM AchievementTriggers
                WHERE AchievementTriggers.CoordinateId = Coordinates.Id
            );
        ");

        _records.Clear();
    }

    public void OnAssetFound(AchievementTrigger asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset));
    }

    private AchievementTriggerDBRecord CreateRecord(AchievementTrigger achievementTrigger)
    {
        var coordinate = new CoordinateDBRecord
        {
            Scene = achievementTrigger.gameObject.scene.name,
            X = achievementTrigger.transform.position.x,
            Y = achievementTrigger.transform.position.y,
            Z = achievementTrigger.transform.position.z,
            Category = nameof(CoordinateCategory.AchievementTrigger)
        };

        _db.Insert(coordinate);

        return new AchievementTriggerDBRecord
        {
            CoordinateId = coordinate.Id,
            AchievementName = achievementTrigger.AchievementName
        };
    }
}