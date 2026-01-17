#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;

/// <summary>
/// Extracts item drop data from the Misc component's item lists.
/// Currently handles FossilGame (Braxonian Fossil drops).
///
/// Note: This listener stores stable keys during OnAssetFound and
/// processes them in OnScanFinished, because the Items table doesn't exist
/// until ItemListener.OnScanFinished has run.
/// </summary>
public class MiscListener : IAssetScanListener<Misc>
{
    private readonly SQLiteConnection _db;
    private readonly List<ItemDropRecord> _records = new();

    // Spell stable key that triggers fossil drops
    private const string BreakFossilSpellKey = "spell:none - break fossil";

    // Store stable keys immediately (Unity objects can become null after scene changes)
    private readonly List<string> _fossilGameStableKeys = new();

    public MiscListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnAssetFound(Misc asset)
    {
        Debug.Log($"[{GetType().Name}] Found Misc component");

        // Store the stable keys immediately - Unity objects may become invalid later
        if (asset.FossilGame != null && asset.FossilGame.Count > 0)
        {
            foreach (var item in asset.FossilGame)
            {
                if (item != null)
                {
                    _fossilGameStableKeys.Add(StableKeyGenerator.ForItem(item));
                }
            }
            Debug.Log($"[{GetType().Name}] Stored {_fossilGameStableKeys.Count} FossilGame stable keys for later processing");
        }
        else
        {
            Debug.LogWarning($"[{GetType().Name}] FossilGame list is null or empty");
        }
    }

    public void OnScanFinished()
    {
        // Process stored fossil game stable keys now that Items table exists
        ProcessFossilGame();

        _db.CreateTable<ItemDropRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ItemDropRecord>();
            _db.InsertAll(_records);
        });

        Debug.Log($"[{GetType().Name}] Wrote {_records.Count} item drop records");
        _records.Clear();
        _fossilGameStableKeys.Clear();
    }

    /// <summary>
    /// Process the stored FossilGame stable keys to extract Braxonian Fossil drop data.
    /// Items appear multiple times in the list to weight their drop probability.
    /// </summary>
    private void ProcessFossilGame()
    {
        if (_fossilGameStableKeys.Count == 0)
        {
            Debug.LogWarning($"[{GetType().Name}] No FossilGame items to process");
            return;
        }

        // Find the source item (the one that triggers Break Fossil spell)
        var sourceItemStableKey = FindSourceItemForSpell(BreakFossilSpellKey);
        if (string.IsNullOrEmpty(sourceItemStableKey))
        {
            Debug.LogError($"[{GetType().Name}] Could not find source item for spell '{BreakFossilSpellKey}'");
            return;
        }

        Debug.Log($"[{GetType().Name}] Found source item: {sourceItemStableKey}");

        // Count occurrences of each item in the list
        var itemCounts = new Dictionary<string, int>();
        int totalCount = 0;

        foreach (var stableKey in _fossilGameStableKeys)
        {
            if (!itemCounts.ContainsKey(stableKey))
            {
                itemCounts[stableKey] = 0;
            }
            itemCounts[stableKey]++;
            totalCount++;
        }

        if (totalCount == 0)
        {
            Debug.LogWarning($"[{GetType().Name}] FossilGame list has no valid items");
            return;
        }

        Debug.Log($"[{GetType().Name}] FossilGame has {totalCount} total entries, {itemCounts.Count} unique items");

        // Create records with calculated probabilities
        foreach (var kvp in itemCounts)
        {
            var dropProbability = Math.Round((double)kvp.Value / totalCount * 100.0, 2);

            _records.Add(new ItemDropRecord
            {
                SourceItemStableKey = sourceItemStableKey,
                DroppedItemStableKey = kvp.Key,
                DropProbability = dropProbability,
                IsGuaranteed = true // One item from this pool always drops
            });

            Debug.Log($"[{GetType().Name}] {kvp.Key}: {kvp.Value}/{totalCount} = {dropProbability}%");
        }
    }

    /// <summary>
    /// Find the item that has the given spell as its click effect.
    /// </summary>
    private string? FindSourceItemForSpell(string spellStableKey)
    {
        var query = @"
            SELECT StableKey
            FROM Items
            WHERE ItemEffectOnClickStableKey = ?
            LIMIT 1
        ";

        try
        {
            var result = _db.Query<ItemStableKeyResult>(query, spellStableKey);
            return result.FirstOrDefault()?.StableKey;
        }
        catch (Exception ex)
        {
            Debug.LogError($"[{GetType().Name}] Failed to query source item: {ex.Message}");
            return null;
        }
    }

    private class ItemStableKeyResult
    {
        public string StableKey { get; set; } = string.Empty;
    }
}
