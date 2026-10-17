#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class SpawnPointTriggerListener : IAssetScanListener<SpawnPointTrigger>
{
    private const float AltSpawnChance = 0.0001f;

    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characterKeyResolver;
    private readonly List<SpawnPointTriggerRecord> _triggerRecords = new();
    private readonly List<SpawnPointTriggerCharacterRecord> _characterRecords = new();
    private readonly ActivationTargetResolver _activationTargets;

    public SpawnPointTriggerListener(
        SQLiteConnection db,
        CharacterStableKeyResolver characterKeyResolver,
        ActivationTargetResolver activationTargets
    )
    {
        _db = db;
        _characterKeyResolver = characterKeyResolver;
        _activationTargets = activationTargets;
    }

    public void OnAssetFound(SpawnPointTrigger asset)
    {
        if (!asset.gameObject.scene.IsValid())
            return;

        if (asset.SpawnSpots == null || asset.SpawnSpots.Count == 0)
        {
            Debug.LogWarning(
                $"[SpawnPointTriggerListener] Trigger '{asset.gameObject.name}' has no SpawnSpots, skipping"
            );
            return;
        }

        var characterChances = BuildCharacterChances(asset);
        if (characterChances.Count == 0)
        {
            return;
        }

        var scene = asset.gameObject.scene.name;
        var isEnabledByDefault = !IsDisabledAtRuntimeStart(asset);
        for (int index = 0; index < asset.SpawnSpots.Count; index++)
        {
            var spawnSpot = asset.SpawnSpots[index];
            if (spawnSpot == null)
            {
                continue;
            }

            var position = spawnSpot.transform.position;
            var stableKey = _activationTargets.GetTriggerSpawnKey(asset, index);

            _triggerRecords.Add(
                new SpawnPointTriggerRecord
                {
                    StableKey = stableKey,
                    Scene = scene,
                    X = position.x,
                    Y = position.y,
                    Z = position.z,
                    IsEnabledByDefault = isEnabledByDefault,
                }
            );

            foreach (var characterChance in characterChances)
            {
                _characterRecords.Add(
                    new SpawnPointTriggerCharacterRecord
                    {
                        SpawnPointTriggerStableKey = stableKey,
                        CharacterStableKey = characterChance.Key,
                        SpawnChance = characterChance.Value,
                    }
                );
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

            if (
                shiverEvent.SpawnTriggers != null
                && shiverEvent.SpawnTriggers.Contains(trigger.gameObject)
            )
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
        string sourceLabel
    )
    {
        if (spawnable == null || spawnChance <= 0f)
        {
            return;
        }

        var character = spawnable.GetComponent<Character>();
        if (character == null)
        {
            Debug.LogWarning(
                $"[SpawnPointTriggerListener] {sourceLabel} '{spawnable.name}' has no Character component, skipping"
            );
            return;
        }

        var characterStableKey = _characterKeyResolver.GetStableKey(character);
        if (!characterChances.TryAdd(characterStableKey, spawnChance))
        {
            characterChances[characterStableKey] += spawnChance;
        }
    }
}
