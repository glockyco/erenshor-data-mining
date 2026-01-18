#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;

public class SpawnPointListener : IAssetScanListener<SpawnPoint>
{
    private readonly SQLiteConnection _db;
    private readonly List<SpawnPointRecord> _spawnPointRecords = new();
    private readonly List<SpawnPointCharacterRecord> _spawnPointCharacterRecords = new();
    private readonly List<SpawnPointStopQuestRecord> _spawnPointStopQuestRecords = new();
    private readonly List<SpawnPointPatrolPointRecord> _spawnPointPatrolPointRecords = new();

    // Spawn delay multipliers from GameManager.SpawnTimeMod (lines 209-224)
    private const float SpawnDelayMultiplier2 = 1.1f;  // 1-2 group members
    private const float SpawnDelayMultiplier3 = 1.5f;  // 3 group members
    private const float SpawnDelayMultiplier4 = 1.8f;  // 4 group members

    public SpawnPointListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<SpawnPointRecord>();
        _db.CreateTable<SpawnPointCharacterRecord>();

        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<SpawnPointRecord>();
            _db.DeleteAll<SpawnPointCharacterRecord>();

            _db.InsertAll(_spawnPointRecords);
            _db.InsertAll(_spawnPointCharacterRecords);
        });

        _spawnPointRecords.Clear();
        _spawnPointCharacterRecords.Clear();

        // Create and insert junction table records after parent records are inserted
        _db.CreateTable<SpawnPointStopQuestRecord>();
        _db.CreateTable<SpawnPointPatrolPointRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<SpawnPointStopQuestRecord>();
            _db.DeleteAll<SpawnPointPatrolPointRecord>();
            _db.InsertAll(_spawnPointStopQuestRecords);
            _db.InsertAll(_spawnPointPatrolPointRecords);
        });
        _spawnPointStopQuestRecords.Clear();
        _spawnPointPatrolPointRecords.Clear();
    }

    public void OnAssetFound(SpawnPoint asset)
    {
        var scene = asset.gameObject.scene.name;
        var x = asset.transform.position.x;
        var y = asset.transform.position.y;
        var z = asset.transform.position.z;
        var stableKey = StableKeyGenerator.ForSpawnPoint(scene, x, y, z);

        var spawnPointRecord = CreateSpawnPointRecord(asset, stableKey, scene, x, y, z);
        _spawnPointRecords.Add(spawnPointRecord);

        var spawnPointCharacterRecords = CreateSpawnPointCharacterRecords(asset, stableKey);
        _spawnPointCharacterRecords.AddRange(spawnPointCharacterRecords);

        _spawnPointStopQuestRecords.AddRange(CreateSpawnPointStopQuestRecords(asset, stableKey));
        _spawnPointPatrolPointRecords.AddRange(CreateSpawnPointPatrolPointRecords(asset, stableKey));
    }

    private SpawnPointRecord CreateSpawnPointRecord(SpawnPoint spawnPoint, string stableKey, string scene, float x, float y, float z)
    {
        // Default value 600f is taken from `SpawnPoint.Start`.
        var spawnDelay = spawnPoint.SpawnDelay == 0f ? 600f : spawnPoint.SpawnDelay;

        return new SpawnPointRecord
        {
            StableKey = stableKey,
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            IsEnabled = spawnPoint.isActiveAndEnabled,
            RareNPCChance = spawnPoint.RareNPCChance,
            LevelMod = spawnPoint.levelMod,
            SpawnDelay1 = spawnDelay,
            SpawnDelay2 = spawnDelay / SpawnDelayMultiplier2,
            SpawnDelay3 = spawnDelay / SpawnDelayMultiplier3,
            SpawnDelay4 = spawnDelay / SpawnDelayMultiplier4,
            Staggerable = spawnPoint.staggerable,
            StaggerMod = spawnPoint.staggerMod,
            NightSpawn = spawnPoint.NightSpawn,
            PatrolPoints = spawnPoint.PatrolPoints != null ? string.Join(", ", spawnPoint.PatrolPoints.Select(t => t.position.ToString())) : null,
            LoopPatrol = spawnPoint.LoopPatrol,
            RandomWanderRange = spawnPoint.RandomWanderRange,
            SpawnUponQuestCompleteStableKey = spawnPoint.SpawnUponQuestComplete != null
                ? StableKeyGenerator.ForQuest(spawnPoint.SpawnUponQuestComplete)
                : null,
            ProtectorStableKey = GetProtectorStableKey(spawnPoint),
        };
    }

    private List<SpawnPointCharacterRecord> CreateSpawnPointCharacterRecords(SpawnPoint spawnPoint, string spawnPointStableKey)
    {
        // Use Character stable key for grouping
        var characterData = new Dictionary<string, (float spawnChance, bool isCommon, bool isRare)>();

        float rareNpcChance = spawnPoint.RareSpawns.Count == 0 ? 0 : spawnPoint.RareNPCChance;
        float commonNpcChance = 100.0f - rareNpcChance;

        // Rare spawns
        if (spawnPoint.RareSpawns is { Count: > 0 })
        {
            var rareSpawnChance = rareNpcChance / spawnPoint.RareSpawns.Count;
            foreach (var rareSpawn in spawnPoint.RareSpawns)
            {
                var character = rareSpawn.GetComponent<Character>();
                if (character == null)
                {
                    UnityEngine.Debug.LogWarning($"[SpawnPointListener] RareSpawn GameObject '{rareSpawn.name}' has no Character component, skipping");
                    continue;
                }
                var characterStableKey = StableKeyGenerator.ForCharacter(character);

                if (!characterData.ContainsKey(characterStableKey))
                {
                    characterData[characterStableKey] = (0f, false, false);
                }

                var entry = characterData[characterStableKey];
                entry.spawnChance += rareSpawnChance;
                entry.isRare = true;
                characterData[characterStableKey] = entry;
            }
        }

        // Common spawns
        if (spawnPoint.CommonSpawns is { Count: > 0 })
        {
            var commonSpawnChance = commonNpcChance / spawnPoint.CommonSpawns.Count;
            foreach (var commonSpawn in spawnPoint.CommonSpawns)
            {
                var character = commonSpawn.GetComponent<Character>();
                if (character == null)
                {
                    UnityEngine.Debug.LogWarning($"[SpawnPointListener] CommonSpawn GameObject '{commonSpawn.name}' has no Character component, skipping");
                    continue;
                }
                var characterStableKey = StableKeyGenerator.ForCharacter(character);

                if (!characterData.ContainsKey(characterStableKey))
                {
                    characterData[characterStableKey] = (0f, false, false);
                }

                var entry = characterData[characterStableKey];
                entry.spawnChance += commonSpawnChance;
                entry.isCommon = true;
                characterData[characterStableKey] = entry;
            }
        }

        // Create records
        var records = new List<SpawnPointCharacterRecord>();
        foreach (var kvp in characterData)
        {
            records.Add(new SpawnPointCharacterRecord
            {
                SpawnPointStableKey = spawnPointStableKey,
                CharacterStableKey = kvp.Key,
                SpawnChance = kvp.Value.spawnChance,
                IsCommon = kvp.Value.isCommon,
                IsRare = kvp.Value.isRare,
            });
        }

        return records;
    }

    private List<SpawnPointStopQuestRecord> CreateSpawnPointStopQuestRecords(SpawnPoint spawnPoint, string spawnPointStableKey)
    {
        var records = new List<SpawnPointStopQuestRecord>();
        var seenQuestStableKeys = new HashSet<string>();

        if (spawnPoint.StopIfQuestComplete != null && spawnPoint.StopIfQuestComplete.Count > 0)
        {
            foreach (var quest in spawnPoint.StopIfQuestComplete)
            {
                if (quest != null && !string.IsNullOrEmpty(quest.DBName))
                {
                    var questStableKey = StableKeyGenerator.ForQuest(quest);
                    if (seenQuestStableKeys.Add(questStableKey))
                    {
                        records.Add(new SpawnPointStopQuestRecord
                        {
                            SpawnPointStableKey = spawnPointStableKey,
                            QuestStableKey = questStableKey
                        });
                    }
                }
            }
        }

        return records;
    }

    private List<SpawnPointPatrolPointRecord> CreateSpawnPointPatrolPointRecords(SpawnPoint spawnPoint, string spawnPointStableKey)
    {
        var records = new List<SpawnPointPatrolPointRecord>();

        if (spawnPoint.PatrolPoints != null && spawnPoint.PatrolPoints.Count > 0)
        {
            for (int i = 0; i < spawnPoint.PatrolPoints.Count; i++)
            {
                var patrolPoint = spawnPoint.PatrolPoints[i];
                if (patrolPoint != null)
                {
                    records.Add(new SpawnPointPatrolPointRecord
                    {
                        SpawnPointStableKey = spawnPointStableKey,
                        SequenceIndex = i,
                        X = patrolPoint.position.x,
                        Y = patrolPoint.position.y,
                        Z = patrolPoint.position.z
                    });
                }
            }
        }

        return records;
    }

    private string? GetProtectorStableKey(SpawnPoint spawnPoint)
    {
        if (spawnPoint.Protector == null)
            return null;

        var character = spawnPoint.Protector.GetComponent<Character>();
        if (character == null)
        {
            UnityEngine.Debug.LogWarning($"[SpawnPointListener] Protector GameObject '{spawnPoint.Protector.name}' at {spawnPoint.transform.position} has no Character component, skipping");
            return null;
        }

        return StableKeyGenerator.ForCharacter(character);
    }
}
