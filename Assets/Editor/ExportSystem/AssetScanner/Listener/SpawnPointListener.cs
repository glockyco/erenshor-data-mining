#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;
using static CoordinateRecord;

public class SpawnPointListener : IAssetScanListener<SpawnPoint>
{
    private readonly SQLiteConnection _db;
    private readonly List<CoordinateRecord> _coordinateRecords = new();
    private readonly List<SpawnPointRecord> _spawnPointRecords = new();
    private readonly List<SpawnPointCharacterRecord> _spawnPointCharacterRecords = new();

    public SpawnPointListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<CoordinateRecord>();
        _db.CreateTable<SpawnPointRecord>();
        _db.CreateTable<SpawnPointCharacterRecord>();
        
        _db.RunInTransaction(() =>
        {
            _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.SpawnPoint));
            _db.DeleteAll<SpawnPointRecord>();
            _db.DeleteAll<SpawnPointCharacterRecord>();
            
            _db.InsertAll(_coordinateRecords);
            _db.InsertAll(_spawnPointRecords);
            _db.InsertAll(_spawnPointCharacterRecords);
        });
        
        _coordinateRecords.Clear();
        _spawnPointRecords.Clear();
        _spawnPointCharacterRecords.Clear();
    }

    public void OnAssetFound(SpawnPoint asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var coordinateRecord = CreateCoordinateRecord(asset);
        var spawnPointRecord = CreateSpawnPointRecord(asset, coordinateRecord.Id);
        coordinateRecord.SpawnPointId = spawnPointRecord.Id;
        
        _coordinateRecords.Add(coordinateRecord);
        _spawnPointRecords.Add(spawnPointRecord);
        
        var spawnPointCharacterRecords = CreateSpawnPointCharacterRecords(asset, spawnPointRecord.Id);
        _spawnPointCharacterRecords.AddRange(spawnPointCharacterRecords);
    }

    private CoordinateRecord CreateCoordinateRecord(SpawnPoint spawnPoint)
    {
        return new CoordinateRecord
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
        // Default value 600f is taken from `SpawnPoint.Start`.
        var spawnDelay = spawnPoint.SpawnDelay == 0f ? 600f : spawnPoint.SpawnDelay;
        
        return new SpawnPointRecord
        {
            Id = TableIdGenerator.NextId(SpawnPointRecord.TableName),
            CoordinateId = coordinateId,
            IsEnabled = spawnPoint.isActiveAndEnabled,
            RareNPCChance = spawnPoint.RareNPCChance,
            LevelMod = spawnPoint.levelMod,
            SpawnDelay1 = spawnDelay,
            SpawnDelay2 = spawnDelay / 1.1f, // See: GameManager.SpawnTimeMod
            SpawnDelay3 = spawnDelay / 1.8f, // See: GameManager.SpawnTimeMod
            SpawnDelay4 = spawnDelay / 1.8f, // See: GameManager.SpawnTimeMod
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