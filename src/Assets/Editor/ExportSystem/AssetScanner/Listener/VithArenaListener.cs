#nullable enable

using System.Collections.Generic;
using System.Reflection;
using SQLite;
using UnityEngine;

public class VithArenaListener : IAssetScanListener<VithArena>
{
    private const int MaxRounds = 8;

    private static readonly BindingFlags FieldFlags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characterKeyResolver;
    private readonly List<ArenaRoundRecord> _roundRecords = new();
    private readonly List<ArenaRoundEnemyRecord> _enemyRecords = new();

    public VithArenaListener(SQLiteConnection db, CharacterStableKeyResolver characterKeyResolver)
    {
        _db = db;
        _characterKeyResolver = characterKeyResolver;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<ArenaRoundRecord>();
        _db.CreateTable<ArenaRoundEnemyRecord>();
        _db.DeleteAll<ArenaRoundEnemyRecord>();
        _db.DeleteAll<ArenaRoundRecord>();
        _roundRecords.Clear();
        _enemyRecords.Clear();
    }

    public void OnScanFinished()
    {
        _db.RunInTransaction(() =>
        {
            _db.InsertAll(_roundRecords);
            _db.InsertAll(_enemyRecords);
        });
        _roundRecords.Clear();
        _enemyRecords.Clear();
    }

    public void OnAssetFound(VithArena asset)
    {
        if (asset == null)
        {
            return;
        }

        var scene = asset.gameObject.scene.name;
        if (string.IsNullOrEmpty(scene))
        {
            Debug.LogWarning($"[{GetType().Name}] VithArena on prefab '{asset.gameObject.name}' has no scene; skipping");
            return;
        }

        var awardChests = GetFieldValue<List<GameObject>>(asset, "AwardChests");
        if (awardChests == null || awardChests.Count == 0)
        {
            Debug.LogWarning($"[{GetType().Name}] VithArena '{asset.gameObject.name}' has no award chests; skipping");
            return;
        }

        for (var roundIndex = 1; roundIndex <= MaxRounds; roundIndex++)
        {
            var coin = GetFieldValue<Item>(asset, $"Coin{roundIndex}");
            var fight = GetFieldValue<List<GameObject>>(asset, $"Coin{roundIndex}Fight");
            var awardChest = roundIndex <= awardChests.Count ? awardChests[roundIndex - 1] : null;

            if (coin == null && fight == null && awardChest == null)
            {
                continue;
            }

            if (coin == null)
            {
                Debug.LogWarning($"[{GetType().Name}] VithArena '{asset.gameObject.name}' round {roundIndex} has no coin; skipping");
                continue;
            }
            if (fight == null || fight.Count == 0)
            {
                Debug.LogWarning($"[{GetType().Name}] VithArena '{asset.gameObject.name}' round {roundIndex} has no fight list; skipping");
                continue;
            }
            if (awardChest == null)
            {
                Debug.LogWarning($"[{GetType().Name}] VithArena '{asset.gameObject.name}' round {roundIndex} has no award chest; skipping");
                continue;
            }

            var chestCharacter = awardChest.GetComponent<Character>();
            if (chestCharacter == null)
            {
                Debug.LogWarning($"[{GetType().Name}] VithArena '{asset.gameObject.name}' round {roundIndex} award chest '{awardChest.name}' has no Character component; skipping");
                continue;
            }

            var stableKey = StableKeyGenerator.ForArenaRound(scene, asset.gameObject.name, roundIndex);
            _roundRecords.Add(new ArenaRoundRecord
            {
                StableKey = stableKey,
                Scene = scene,
                ArenaObjectName = asset.gameObject.name,
                RoundIndex = roundIndex,
                CoinItemStableKey = StableKeyGenerator.ForItem(coin),
                AwardChestCharacterStableKey = _characterKeyResolver.GetStableKey(chestCharacter),
            });

            for (var sequenceIndex = 0; sequenceIndex < fight.Count; sequenceIndex++)
            {
                var enemy = fight[sequenceIndex];
                if (enemy == null)
                {
                    Debug.LogWarning($"[{GetType().Name}] VithArena '{asset.gameObject.name}' round {roundIndex} enemy {sequenceIndex} is null; skipping enemy");
                    continue;
                }

                var enemyCharacter = enemy.GetComponent<Character>();
                if (enemyCharacter == null)
                {
                    Debug.LogWarning($"[{GetType().Name}] VithArena '{asset.gameObject.name}' round {roundIndex} enemy '{enemy.name}' has no Character component; skipping enemy");
                    continue;
                }

                _enemyRecords.Add(new ArenaRoundEnemyRecord
                {
                    ArenaRoundStableKey = stableKey,
                    SequenceIndex = sequenceIndex,
                    EnemyCharacterStableKey = _characterKeyResolver.GetStableKey(enemyCharacter),
                });
            }
        }
    }

    private static T? GetFieldValue<T>(VithArena asset, string fieldName) where T : class
    {
        var field = asset.GetType().GetField(fieldName, FieldFlags);
        return field?.GetValue(asset) as T;
    }
}
