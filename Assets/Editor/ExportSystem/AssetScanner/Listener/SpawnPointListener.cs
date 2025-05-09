#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;

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

    public void OnScanFinished()
    {
        _db.CreateTable<SpawnPointDBRecord>();
        _db.CreateTable<SpawnPointCharacterDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<SpawnPointDBRecord>();
            _db.DeleteAll<SpawnPointCharacterDBRecord>();
            _db.InsertAll(_spawnPointRecords);
            _db.InsertAll(_spawnPointCharacterRecords);
        });
        _spawnPointRecords.Clear();
        _spawnPointCharacterRecords.Clear();
        _spawnPointCounts.Clear();
    }

    public void OnAssetFound(SpawnPoint asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var spawnPointRecord = CreateSpawnPointRecord(asset);
        var spawnPointCharacterRecords = CreateSpawnPointCharacterRecords(asset, spawnPointRecord.Id);

        _spawnPointRecords.Add(spawnPointRecord);
        _spawnPointCharacterRecords.AddRange(spawnPointCharacterRecords);
    }

    private SpawnPointDBRecord CreateSpawnPointRecord(SpawnPoint spawnPoint)
    {
        var baseId = spawnPoint.gameObject.scene.name + spawnPoint.transform.position;
        var spawnPointIndex = _spawnPointCounts.GetValueOrDefault(baseId, 0);
        _spawnPointCounts[baseId] = spawnPointIndex + 1;
        var finalId = baseId + (spawnPointIndex > 0 ? $"_{spawnPointIndex + 1}" : "");
        
        return new SpawnPointDBRecord
        {
            Id = finalId,
            SceneName = spawnPoint.gameObject.scene.name,
            PositionX = spawnPoint.transform.position.x,
            PositionY = spawnPoint.transform.position.y,
            PositionZ = spawnPoint.transform.position.z,
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
    
    private List<SpawnPointCharacterDBRecord> CreateSpawnPointCharacterRecords(SpawnPoint spawnPoint, string spawnPointId)
    {
        var records = new List<SpawnPointCharacterDBRecord>();

        float rareNpcChance = spawnPoint.RareNPCChance;
        float commonNpcChance = 100.0f - rareNpcChance;

        if (spawnPoint.RareSpawns is { Count: > 0 })
        {
            var rareSpawnChance = rareNpcChance / spawnPoint.RareSpawns.Count;
            for (var i = 0; i < spawnPoint.RareSpawns.Count; i++)
            {
                var rareSpawn = spawnPoint.RareSpawns[i];
                records.Add(CreateSpawnPointCharacterRecord(spawnPointId, rareSpawn, "Rare", i, rareSpawnChance));
            }
        }

        if (spawnPoint.CommonSpawns is { Count: > 0 })
        {
            var commonSpawnChance = commonNpcChance / spawnPoint.CommonSpawns.Count;
            for (var i = 0; i < spawnPoint.CommonSpawns.Count; i++)
            {
                var commonSpawn = spawnPoint.CommonSpawns[i];
                records.Add(CreateSpawnPointCharacterRecord(spawnPointId, commonSpawn, "Common", i, commonSpawnChance));
            }
        }

        return records;
    }

    private SpawnPointCharacterDBRecord CreateSpawnPointCharacterRecord(
        string spawnPointId,
        GameObject prefab,
        string spawnType,
        int spawnListIndex,
        float spawnChance)
    {
        var path = AssetDatabase.GetAssetPath(prefab);
        var guid = AssetDatabase.AssetPathToGUID(path);

        return new SpawnPointCharacterDBRecord
        {
            SpawnPointId = spawnPointId,
            CharacterPrefabGuid = guid,
            SpawnType = spawnType,
            SpawnListIndex = spawnListIndex,
            SpawnChance = spawnChance,
        };
    }
}