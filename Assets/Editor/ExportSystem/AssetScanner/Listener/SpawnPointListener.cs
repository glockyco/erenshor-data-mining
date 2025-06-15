#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;
using static CoordinateDBRecord;

public class SpawnPointListener : IAssetScanListener<SpawnPoint>
{
    private readonly SQLiteConnection _db;
    private readonly List<SpawnPointDBRecord> _spawnPointRecords = new();
    private readonly List<SpawnPointCharacterDBRecord> _spawnPointCharacterRecords = new();
    private readonly Dictionary<string, int> _spawnPointCounts = new();

    public SpawnPointListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateDBRecord>();
        _db.CreateTable<SpawnPointDBRecord>();
        _db.CreateTable<SpawnPointCharacterDBRecord>();
        
        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.SpawnPoint));
        _db.DeleteAll<SpawnPointDBRecord>();
        _db.DeleteAll<SpawnPointCharacterDBRecord>();
    }
    
    public void OnScanFinished()
    {
        _db.Execute(@"
            UPDATE Coordinates
            SET SpawnPointId = (
                SELECT Id
                FROM SpawnPoints
                WHERE SpawnPoints.CoordinateId = Coordinates.Id
            )
            WHERE EXISTS (
                SELECT 1
                FROM SpawnPoints
                WHERE SpawnPoints.CoordinateId = Coordinates.Id
            );
        ");
    }

    public void OnAssetFound(SpawnPoint asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var coordinateRecord = CreateCoordinateRecord(asset);
        _db.Insert(coordinateRecord);
        
        var spawnPointRecord = CreateSpawnPointRecord(asset, coordinateRecord.Id);
        _db.Insert(spawnPointRecord);
        
        var spawnPointCharacterRecords = CreateSpawnPointCharacterRecords(asset, spawnPointRecord.Id);
        _db.InsertAll(spawnPointCharacterRecords);
    }

    private CoordinateDBRecord CreateCoordinateRecord(SpawnPoint spawnPoint)
    {
        return new CoordinateDBRecord
        {
            Scene = spawnPoint.gameObject.scene.name,
            X = spawnPoint.transform.position.x,
            Y = spawnPoint.transform.position.y,
            Z = spawnPoint.transform.position.z,
            Category = nameof(CoordinateCategory.SpawnPoint)
        };
    }

    private SpawnPointDBRecord CreateSpawnPointRecord(SpawnPoint spawnPoint, int coordinateId)
    {
        var baseId = spawnPoint.gameObject.scene.name + spawnPoint.transform.position;
        var spawnPointIndex = _spawnPointCounts.GetValueOrDefault(baseId, 0);
        _spawnPointCounts[baseId] = spawnPointIndex + 1;
        var finalId = baseId + (spawnPointIndex > 0 ? $"_{spawnPointIndex + 1}" : "");
        
        return new SpawnPointDBRecord
        {
            CoordinateId = coordinateId,
            IsEnabled = spawnPoint.isActiveAndEnabled,
            RareNPCChance = spawnPoint.RareNPCChance,
            LevelMod = spawnPoint.levelMod,
            SpawnDelay = spawnPoint.SpawnDelay,
            Staggerable = spawnPoint.staggerable,
            StaggerMod = spawnPoint.staggerMod,
            NightSpawn = spawnPoint.NightSpawn,
            PatrolPoints = spawnPoint.PatrolPoints != null ? string.Join(", ", spawnPoint.PatrolPoints.Select(t => t.position.ToString())) : null,
            LoopPatrol = spawnPoint.LoopPatrol,
            RandomWanderRange = spawnPoint.RandomWanderRange,
            SpawnUponQuestCompleteDBName = spawnPoint.SpawnUponQuestComplete?.DBName,
            StopIfQuestCompleteDBNames = spawnPoint.StopIfQuestComplete?.Count > 0 ? string.Join(", ", spawnPoint.StopIfQuestComplete.Where(q => q != null && !string.IsNullOrEmpty(q.DBName)) .Select(q => q.DBName)) : null,
            ProtectorName = (spawnPoint.Protector != null) ? spawnPoint.Protector.name : null,
        };
    }

    private List<SpawnPointCharacterDBRecord> CreateSpawnPointCharacterRecords(SpawnPoint spawnPoint, int spawnPointId)
    {
        var records = new List<SpawnPointCharacterDBRecord>();
        var spawnChancesByGuid = new Dictionary<string, float>();

        float rareNpcChance = spawnPoint.RareNPCChance;
        float commonNpcChance = 100.0f - rareNpcChance;

        // First pass: Calculate individual spawn chances and accumulate totals by GUID
        if (spawnPoint.RareSpawns is { Count: > 0 })
        {
            var rareSpawnChance = rareNpcChance / spawnPoint.RareSpawns.Count;
            for (var i = 0; i < spawnPoint.RareSpawns.Count; i++)
            {
                var rareSpawn = spawnPoint.RareSpawns[i];
                var path = AssetDatabase.GetAssetPath(rareSpawn);
                var guid = AssetDatabase.AssetPathToGUID(path);

                spawnChancesByGuid.TryAdd(guid, 0f);
                spawnChancesByGuid[guid] += rareSpawnChance;

                records.Add(new SpawnPointCharacterDBRecord
                {
                    SpawnPointId = spawnPointId,
                    CharacterPrefabGuid = guid,
                    SpawnType = "Rare",
                    SpawnListIndex = i,
                    SpawnChance = rareSpawnChance,
                    // TotalSpawnChance will be set in the second pass
                });
            }
        }

        if (spawnPoint.CommonSpawns is { Count: > 0 })
        {
            var commonSpawnChance = commonNpcChance / spawnPoint.CommonSpawns.Count;
            for (var i = 0; i < spawnPoint.CommonSpawns.Count; i++)
            {
                var commonSpawn = spawnPoint.CommonSpawns[i];
                var path = AssetDatabase.GetAssetPath(commonSpawn);
                var guid = AssetDatabase.AssetPathToGUID(path);

                spawnChancesByGuid.TryAdd(guid, 0f);
                spawnChancesByGuid[guid] += commonSpawnChance;

                records.Add(new SpawnPointCharacterDBRecord
                {
                    SpawnPointId = spawnPointId,
                    CharacterPrefabGuid = guid,
                    SpawnType = "Common",
                    SpawnListIndex = i,
                    SpawnChance = commonSpawnChance,
                    // TotalSpawnChance will be set in the second pass
                });
            }
        }

        // Second pass: Set TotalSpawnChance for each record
        foreach (var record in records)
        {
            record.TotalSpawnChance = spawnChancesByGuid[record.CharacterPrefabGuid];
        }

        return records;
    }
}