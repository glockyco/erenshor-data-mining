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

    public SpawnPointListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateDBRecord>();
        _db.CreateTable<SpawnPointRecord>();
        _db.CreateTable<SpawnPointCharacterRecord>();
        
        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.SpawnPoint));
        _db.DeleteAll<SpawnPointRecord>();
        _db.DeleteAll<SpawnPointCharacterRecord>();
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

    private SpawnPointRecord CreateSpawnPointRecord(SpawnPoint spawnPoint, int coordinateId)
    {
        return new SpawnPointRecord
        {
            CoordinateId = coordinateId,
            IsEnabled = spawnPoint.isActiveAndEnabled,
            RareNPCChance = spawnPoint.RareNPCChance,
            LevelMod = spawnPoint.levelMod,
            SpawnDelay1 = spawnPoint.SpawnDelay,
            SpawnDelay2 = spawnPoint.SpawnDelay / 1.1f, // See: GameManager.SpawnTimeMod
            SpawnDelay3 = spawnPoint.SpawnDelay / 1.8f, // See: GameManager.SpawnTimeMod
            SpawnDelay4 = spawnPoint.SpawnDelay / 1.8f, // See: GameManager.SpawnTimeMod
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

    private List<SpawnPointCharacterRecord> CreateSpawnPointCharacterRecords(SpawnPoint spawnPoint, int spawnPointId)
    {
        // Use GUID as the key for grouping
        var characterData = new Dictionary<string, (float spawnChance, bool isCommon, bool isRare)>();

        float rareNpcChance = spawnPoint.RareSpawns.Count == 0 ? 0 : spawnPoint.RareNPCChance;
        float commonNpcChance = 100.0f - rareNpcChance;

        // Rare spawns
        if (spawnPoint.RareSpawns is { Count: > 0 })
        {
            var rareSpawnChance = rareNpcChance / spawnPoint.RareSpawns.Count;
            foreach (var rareSpawn in spawnPoint.RareSpawns)
            {
                var path = AssetDatabase.GetAssetPath(rareSpawn);
                var guid = AssetDatabase.AssetPathToGUID(path);

                if (!characterData.ContainsKey(guid))
                {
                    characterData[guid] = (0f, false, false);
                }

                var entry = characterData[guid];
                entry.spawnChance += rareSpawnChance;
                entry.isRare = true;
                characterData[guid] = entry;
            }
        }

        // Common spawns
        if (spawnPoint.CommonSpawns is { Count: > 0 })
        {
            var commonSpawnChance = commonNpcChance / spawnPoint.CommonSpawns.Count;
            foreach (var commonSpawn in spawnPoint.CommonSpawns)
            {
                var path = AssetDatabase.GetAssetPath(commonSpawn);
                var guid = AssetDatabase.AssetPathToGUID(path);

                if (!characterData.ContainsKey(guid))
                {
                    characterData[guid] = (0f, false, false);
                }

                var entry = characterData[guid];
                entry.spawnChance += commonSpawnChance;
                entry.isCommon = true;
                characterData[guid] = entry;
            }
        }

        // Create records
        var records = new List<SpawnPointCharacterRecord>();
        foreach (var kvp in characterData)
        {
            records.Add(new SpawnPointCharacterRecord
            {
                SpawnPointId = spawnPointId,
                CharacterGuid = kvp.Key,
                SpawnChance = kvp.Value.spawnChance,
                IsCommon = kvp.Value.isCommon,
                IsRare = kvp.Value.isRare,
            });
        }

        return records;
    }
}