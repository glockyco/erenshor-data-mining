#nullable enable

using System;
using System.Collections.Generic;
using SQLite;
using UnityEngine;

/// <summary>
/// Exports the knowledge base of simulated-player chat as the game ships it.
/// The game ships one KnowledgeDatabaseAsset, and chat reads its entries by
/// index, so a second asset would make the positions ambiguous.
/// </summary>
public class KnowledgeDatabaseListener : IAssetScanListener<KnowledgeDatabaseAsset>
{
    private readonly SQLiteConnection _db;
    private readonly List<KnowledgeEntryRecord> _entries = new();
    private readonly List<KnowledgeEntryDropRecord> _drops = new();
    private string? _assetName;

    public KnowledgeDatabaseListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<KnowledgeEntryRecord>();
        _db.CreateTable<KnowledgeEntryDropRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<KnowledgeEntryDropRecord>();
            _db.DeleteAll<KnowledgeEntryRecord>();
        });
        _entries.Clear();
        _drops.Clear();
        _assetName = null;
    }

    public void OnAssetFound(KnowledgeDatabaseAsset asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");
        if (_assetName != null)
        {
            throw new InvalidOperationException(
                $"Found a second knowledge base, {asset.name}, after {_assetName}"
            );
        }
        _assetName = asset.name;

        for (var position = 0; position < asset.Entries.Count; position++)
        {
            var entry = asset.Entries[position];
            _entries.Add(
                new KnowledgeEntryRecord
                {
                    Position = position,
                    NPCName = entry.NPCName ?? string.Empty,
                    ZoneName = string.IsNullOrEmpty(entry.ZoneThisLootIsFrom)
                        ? null
                        : entry.ZoneThisLootIsFrom,
                    Level = entry.Level,
                    IsBoss = entry.IsBoss,
                    PrefabPath = entry.PrefabPath ?? string.Empty,
                }
            );
            if (entry.Drops == null)
                continue;
            for (var dropPosition = 0; dropPosition < entry.Drops.Count; dropPosition++)
            {
                _drops.Add(
                    new KnowledgeEntryDropRecord
                    {
                        EntryPosition = position,
                        Position = dropPosition,
                        ItemName = entry.Drops[dropPosition] ?? string.Empty,
                    }
                );
            }
        }
    }

    public void OnScanFinished()
    {
        _db.RunInTransaction(() =>
        {
            _db.InsertAll(_entries);
            _db.InsertAll(_drops);
        });
        _entries.Clear();
        _drops.Clear();
    }
}
