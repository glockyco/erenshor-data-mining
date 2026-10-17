#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using SQLite;
using UnityEditor;
using UnityEngine;

// ZoneAnnounce chooses a registered SpawnPoint at runtime, not the Misc host's position.
public sealed class ZoneWideSpawnListener : IAssetScanListener<Misc>
{
    public const string SpectreRule = "sivakayan_spectres";
    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characterKeys;
    private readonly List<ZoneWideSpawnCandidateRecord> _records = new();
    private int _sources;

    public ZoneWideSpawnListener(SQLiteConnection db, CharacterStableKeyResolver characterKeys)
    {
        _db = db;
        _characterKeys = characterKeys;
    }

    public void OnScanStarted()
    {
        _records.Clear();
        _sources = 0;
    }

    public void OnAssetFound(Misc asset)
    {
        if (!asset.gameObject.scene.IsValid() || PrefabUtility.IsPartOfPrefabAsset(asset))
            return;
        _sources++;
        if (asset.SivakayanSpectres == null || asset.SivakayanSpectres.Count == 0)
            throw new InvalidOperationException("Misc.SivakayanSpectres has no candidates");
        // code-fact: spectres.spawn_selection
        // Preserve every serialized slot. Duplicate prefabs supply their real weights.
        for (int slot = 0; slot < asset.SivakayanSpectres.Count; slot++)
        {
            var prefab = asset.SivakayanSpectres[slot];
            var character = prefab != null ? prefab.GetComponent<Character>() : null;
            if (character == null)
                throw new InvalidOperationException(
                    $"Misc.SivakayanSpectres[{slot}] has no Character"
                );
            _records.Add(
                new ZoneWideSpawnCandidateRecord
                {
                    Key = SpectreRule + ":" + slot.ToString(CultureInfo.InvariantCulture),
                    RuleId = SpectreRule,
                    Slot = slot,
                    CharacterStableKey = _characterKeys.GetStableKey(character),
                }
            );
        }
    }

    public void OnScanFinished()
    {
        if (_sources != 1)
            throw new InvalidOperationException($"Expected one placed Misc, found {_sources}");
        _db.CreateTable<ZoneWideSpawnCandidateRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ZoneWideSpawnCandidateRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }
}
