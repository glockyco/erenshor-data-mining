#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

/// <summary>
/// Exports the characters that each raid plane's <c>PlanarMusicManager</c> names as bosses.
/// The game starts the boss music when the character of <c>BigBossSpawn</c> engages and the
/// mid-boss music for the characters of <c>MidBossSpawns</c>, so these lists are the game's
/// own designation of raid bosses.
/// </summary>
public class PlanarMusicManagerListener : IAssetScanListener<PlanarMusicManager>
{
    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characterKeyResolver;
    private readonly Dictionary<string, PlanarBossRecord> _records = new();

    public PlanarMusicManagerListener(
        SQLiteConnection db,
        CharacterStableKeyResolver characterKeyResolver
    )
    {
        _db = db;
        _characterKeyResolver = characterKeyResolver;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<PlanarBossRecord>();
        _db.DeleteAll<PlanarBossRecord>();
        _records.Clear();
    }

    public void OnScanFinished()
    {
        _db.RunInTransaction(() => _db.InsertAll(_records.Values));
        _records.Clear();
    }

    public void OnAssetFound(PlanarMusicManager asset)
    {
        if (asset == null)
        {
            return;
        }
        var scene = asset.gameObject.scene.name;
        if (string.IsNullOrEmpty(scene))
        {
            Debug.LogWarning(
                $"[{GetType().Name}] PlanarMusicManager on prefab '{asset.gameObject.name}' has no scene; skipping"
            );
            return;
        }
        if (asset.BigBossSpawn != null)
        {
            AddSpawnCharacters(scene, "boss", asset.BigBossSpawn);
        }
        if (asset.MidBossSpawns != null)
        {
            foreach (var spawn in asset.MidBossSpawns)
            {
                if (spawn != null)
                {
                    AddSpawnCharacters(scene, "midboss", spawn);
                }
            }
        }
    }

    private void AddSpawnCharacters(string scene, string role, SpawnPoint spawn)
    {
        var candidates = new List<GameObject>();
        if (spawn.CommonSpawns != null)
        {
            candidates.AddRange(spawn.CommonSpawns);
        }
        if (spawn.RareSpawns != null)
        {
            candidates.AddRange(spawn.RareSpawns);
        }
        foreach (var candidate in candidates)
        {
            var character = candidate != null ? candidate.GetComponent<Character>() : null;
            if (character == null)
            {
                Debug.LogWarning(
                    $"[{GetType().Name}] {scene} {role} spawn '{spawn.name}' lists an object without a Character; skipping"
                );
                continue;
            }
            var characterKey = _characterKeyResolver.GetStableKey(character);
            var key = $"{scene}:{characterKey}";
            if (_records.TryGetValue(key, out var existing))
            {
                // A character on both lists counts as the big boss.
                if (role == "boss")
                {
                    existing.Role = role;
                }
                continue;
            }
            _records[key] = new PlanarBossRecord
            {
                StableKey = key,
                Scene = scene,
                Role = role,
                CharacterStableKey = characterKey,
            };
        }
    }
}
