#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class SpawnPointTriggerListener : IAssetScanListener<SpawnPointTrigger>
{
    private const float AltSpawnChance = 0.01f;

    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characterKeyResolver;
    private readonly List<SpawnPointTriggerRecord> _triggerRecords = new();
    private readonly List<SpawnPointTriggerCharacterRecord> _characterRecords = new();
    private readonly DuplicateKeyTracker _keyTracker = new("SpawnPointTriggerListener");

    public SpawnPointTriggerListener(SQLiteConnection db, CharacterStableKeyResolver characterKeyResolver)
    {
        _db = db;
        _characterKeyResolver = characterKeyResolver;
    }

    public void OnAssetFound(SpawnPointTrigger asset)
    {
        if (asset.SpawnSpots == null || asset.SpawnSpots.Count == 0)
        {
            Debug.LogWarning($"[SpawnPointTriggerListener] Trigger '{asset.gameObject.name}' has no SpawnSpots, skipping");
            return;
        }

        var characterChances = BuildCharacterChances(asset);
        if (characterChances.Count == 0)
        {
            return;
        }

        var scene = asset.gameObject.scene.name;
        var isEnabledByDefault = !IsDisabledAtRuntimeStart(asset);
        foreach (var spawnSpot in asset.SpawnSpots)
        {
            if (spawnSpot == null)
            {
                continue;
            }

            var position = spawnSpot.transform.position;
            var baseKey = StableKeyGenerator.ForSpawnPointTrigger(scene, position.x, position.y, position.z);
            var stableKey = _keyTracker.GetUniqueKey(baseKey, $"{asset.gameObject.name}/{spawnSpot.name}");

            _triggerRecords.Add(new SpawnPointTriggerRecord
            {
                StableKey = stableKey,
                Scene = scene,
                X = position.x,
                Y = position.y,
                Z = position.z,
                IsEnabledByDefault = isEnabledByDefault,
            });

            foreach (var characterChance in characterChances)
            {
                _characterRecords.Add(new SpawnPointTriggerCharacterRecord
                {
                    SpawnPointTriggerStableKey = stableKey,
                    CharacterStableKey = characterChance.Key,
                    SpawnChance = characterChance.Value,
                });
            }
        }
    }

    public void OnScanFinished()
    {
        _db.CreateTable<SpawnPointTriggerRecord>();
        _db.CreateTable<SpawnPointTriggerCharacterRecord>();

        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<SpawnPointTriggerRecord>();
            _db.DeleteAll<SpawnPointTriggerCharacterRecord>();
            _db.InsertAll(_triggerRecords);
            _db.InsertAll(_characterRecords);
        });

        _triggerRecords.Clear();
        _characterRecords.Clear();
    }

    private static bool IsDisabledAtRuntimeStart(SpawnPointTrigger trigger)
    {
        foreach (var shiverEvent in Object.FindObjectsOfType<ShiverEvent>(true))
        {
            if (shiverEvent == null || shiverEvent.gameObject.scene != trigger.gameObject.scene)
            {
                continue;
            }

            if (shiverEvent.SpawnTriggers != null && shiverEvent.SpawnTriggers.Contains(trigger.gameObject))
            {
                return true;
            }
        }

        return !trigger.isActiveAndEnabled;
    }


    private Dictionary<string, float> BuildCharacterChances(SpawnPointTrigger trigger)
    {
        var characterChances = new Dictionary<string, float>();
        var spawnableCount = trigger.Spawnables?.Count ?? 0;

        if (spawnableCount > 0)
        {
            var spawnablesTotalChance = trigger.Alt == null ? 100f : 100f - AltSpawnChance;
            var chancePerSpawnable = spawnablesTotalChance / spawnableCount;
            foreach (var spawnable in trigger.Spawnables)
            {
                AddCharacterChance(characterChances, spawnable, chancePerSpawnable, "Spawnable");
            }
        }

        if (trigger.Alt != null)
        {
            AddCharacterChance(characterChances, trigger.Alt, AltSpawnChance, "Alt");
        }

        return characterChances;
    }

    private void AddCharacterChance(
        Dictionary<string, float> characterChances,
        GameObject? spawnable,
        float spawnChance,
        string sourceLabel)
    {
        if (spawnable == null || spawnChance <= 0f)
        {
            return;
        }

        var character = spawnable.GetComponent<Character>();
        if (character == null)
        {
            Debug.LogWarning(
                $"[SpawnPointTriggerListener] {sourceLabel} '{spawnable.name}' has no Character component, skipping");
            return;
        }

        var characterStableKey = _characterKeyResolver.GetStableKey(character);
        if (!characterChances.TryAdd(characterStableKey, spawnChance))
        {
            characterChances[characterStableKey] += spawnChance;
        }
    }
}
