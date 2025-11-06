#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;
using SQLite;
using UnityEditor;
using UnityEngine;

public class LootTableListener : IAssetScanListener<LootTable>
{
    private readonly SQLiteConnection _db;
    private readonly List<LootTableRecord> _records = new();
    private readonly LootTableProbabilityCalculator _probabilityCalculator = new();

    public LootTableListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<LootTableRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<LootTableRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(LootTable asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var records = CreateRecords(asset);

        // Check for duplicates and skip them
        foreach (var record in records)
        {
            var existingRecord = _records.FirstOrDefault(r =>
                r.CharacterStableKey == record.CharacterStableKey &&
                r.ItemStableKey == record.ItemStableKey);

            if (existingRecord != null)
            {
                UnityEngine.Debug.LogWarning($"[LootTableListener] Duplicate loot drop: Character '{record.CharacterStableKey}' dropping Item '{record.ItemStableKey}'. LootTable asset: '{asset.name}'. Skipping duplicate.");
                continue;
            }

            _records.Add(record);
        }
    }

    private List<LootTableRecord> CreateRecords(LootTable lootTable)
    {
        var perItemDistributions = _probabilityCalculator.CalculatePerItemDropCountDistributions(lootTable);
        var expectedDrops = _probabilityCalculator.ComputeExpectedDrops(perItemDistributions);

        // Get Character component to generate stable key
        var character = lootTable.gameObject.GetComponent<Character>();
        if (character == null)
        {
            Debug.LogWarning($"[{GetType().Name}] LootTable on {lootTable.gameObject.name} has no Character component - skipping");
            return new List<LootTableRecord>();
        }

        var characterStableKey = StableKeyGenerator.ForCharacter(character);

        var records = new List<LootTableRecord>();

        foreach (var item in EnumerateAllUniqueItems(lootTable))
        {
            var itemStableKey = StableKeyGenerator.ForItem(item);

            perItemDistributions.TryGetValue(item.name, out var dist);

            var dropProbability = dist is { Length: > 0 } ? 1.0 - dist[0] : 0.0;
            dropProbability = Math.Round(dropProbability * 100.0, 2); // as percentage

            var dropCountList = new List<DropCountProbability>();
            if (dist != null)
            {
                for (var n = 0; n < dist.Length; ++n)
                {
                    var pct = Math.Round(dist[n] * 100.0, 2);
                    if (pct > 0)
                    {
                        dropCountList.Add(new DropCountProbability { Count = n, Chance = $"{pct}%" });
                    }
                }
            }

            var record = new LootTableRecord
            {
                CharacterStableKey = characterStableKey,
                ItemStableKey = itemStableKey,
                DropProbability = dropProbability,
                ExpectedPerKill = Math.Round(expectedDrops.GetValueOrDefault(item.name, 0.0), 4),
                DropCountDistribution = JsonConvert.SerializeObject(dropCountList),
                IsActual = lootTable.ActualDrops != null && lootTable.ActualDrops.Contains(item),
                IsGuaranteed = lootTable.GuaranteeOneDrop != null && lootTable.GuaranteeOneDrop.Contains(item),
                IsCommon = lootTable.CommonDrop != null && lootTable.CommonDrop.Contains(item),
                IsUncommon = lootTable.UncommonDrop != null && lootTable.UncommonDrop.Contains(item),
                IsRare = lootTable.RareDrop != null && lootTable.RareDrop.Contains(item),
                IsLegendary = lootTable.LegendaryDrop != null && lootTable.LegendaryDrop.Contains(item),
                IsUnique = item.Unique,
                IsVisible = lootTable.VisiblePieces.Select(t => t.name).Contains(item.EquipmentToActivate)
            };
            records.Add(record);
        }

        if (perItemDistributions.TryGetValue(LootTableProbabilityCalculator.WorldDropKey, out var worldDist))
        {
            var worldProb = worldDist is { Length: > 0 } ? 1.0 - worldDist[0] : 0.0;
            worldProb = Math.Round(worldProb * 100.0, 2);

            var worldDropCountList = new List<DropCountProbability>();
            if (worldDist != null)
            {
                for (var n = 0; n < worldDist.Length; ++n)
                {
                    var pct = Math.Round(worldDist[n] * 100.0, 2);
                    if (pct > 0)
                    {
                        worldDropCountList.Add(new DropCountProbability { Count = n, Chance = $"{pct}%" });
                    }
                }
            }

            records.Add(new LootTableRecord
            {
                CharacterStableKey = characterStableKey,
                ItemStableKey = LootTableProbabilityCalculator.WorldDropKey,
                DropProbability = worldProb,
                ExpectedPerKill = Math.Round(expectedDrops.GetValueOrDefault(LootTableProbabilityCalculator.WorldDropKey, 0.0), 4),
                DropCountDistribution = JsonConvert.SerializeObject(worldDropCountList),
                IsGuaranteed = false,
                IsUnique = false,
                IsVisible = false
            });
        }

        return records;
    }

    private static IEnumerable<Item> EnumerateAllUniqueItems(LootTable lootTable)
    {
        var seen = new HashSet<string>();
        foreach (var list in new[]
                 {
                     lootTable.LegendaryDrop,
                     lootTable.RareDrop,
                     lootTable.UncommonDrop,
                     lootTable.CommonDrop,
                     lootTable.GuaranteeOneDrop,
                     lootTable.ActualDrops
                 })
        {
            if (list == null) continue;
            foreach (var item in list)
            {
                if (item is null) continue;
                if (seen.Add(item.Id))
                    yield return item;
            }
        }
    }
    
    private class DropCountProbability
    {
        public int Count { get; set; }
        public string Chance { get; set; }
    }
}