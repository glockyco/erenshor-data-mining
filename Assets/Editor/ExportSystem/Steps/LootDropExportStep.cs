using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEditor;
using UnityEngine;

public class LootDropExportStep : IExportStep
{
    private readonly LootTableProbabilityCalculator _probabilityCalculator;

    public const string CHARACTERS_PATH = "Assets/GameObject"; // Path relative to Assets

    // --- Metadata ---
    public string StepName => "Loot Drops";
    
    public LootDropExportStep(LootTableProbabilityCalculator probabilityCalculator)
    {
        _probabilityCalculator = probabilityCalculator ?? throw new ArgumentNullException(nameof(probabilityCalculator));
    }

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(LootDropDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        reportProgress(0, 0);

        // --- Data Fetching ---
        string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
        var characterPrefabs = guids
            .Select(guid =>
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                return (prefab, guid);
            })
            .Where(item => item.prefab != null && item.prefab.GetComponent<LootTable>() != null)
            .ToList();

        int totalCharacters = characterPrefabs.Count;

        if (totalCharacters == 0)
        {
            reportProgress(0, 0);
            Debug.LogWarning("No character prefabs with LootTable found.");
            return;
        }

        reportProgress(0, totalCharacters);
        await Task.Yield();

        // --- Processing & DB Interaction ---
        int batchSize = 50;
        var batchRecords = new List<LootDropDBRecord>();
        int processedCount = 0;
        int totalRecordCount = 0;

        foreach (var (prefab, guid) in characterPrefabs)
        {
            cancellationToken.ThrowIfCancellationRequested();

            LootTable lootTable = prefab.GetComponent<LootTable>();
            if (lootTable != null)
            {
                // --- Extraction Logic ---
                List<LootDropDBRecord> drops = CollectLootDropsForCharacter(guid, lootTable);
                batchRecords.AddRange(drops);
            }

            processedCount++;

            // --- Batch Insertion ---
            if (batchRecords.Count >= batchSize || (processedCount == totalCharacters && batchRecords.Count > 0))
            {
                try
                {
                    db.RunInTransaction(() =>
                    {
                        db.InsertAll(batchRecords);
                    });
                    totalRecordCount += batchRecords.Count;
                    batchRecords.Clear();
                }
                catch (Exception ex)
                {
                    Debug.LogError($"Error inserting loot drop batch (around character index {processedCount - 1}): {ex.Message}");
                    reportProgress(processedCount, totalCharacters);
                    throw;
                }

                // --- Progress Reporting ---
                reportProgress(processedCount, totalCharacters);
                await Task.Yield();
            }
        }
        
        reportProgress(processedCount, totalCharacters);
        Debug.Log($"Finished exporting {totalRecordCount} loot drops from {processedCount} characters.");
    }

    private List<LootDropDBRecord> CollectLootDropsForCharacter(string guid, LootTable lootTable)
    {
        var lootDrops = new List<LootDropDBRecord>();

        Dictionary<string, double> dropProbabilities = _probabilityCalculator.CalculateDropProbabilities(lootTable);

        void CollectLootDrops(List<Item> items, string dropType)
        {
            if (items != null)
            {
                for (int i = 0; i < items.Count; i++)
                {
                    Item item = items[i];
                    if (item != null && !string.IsNullOrEmpty(item.Id))
                    {
                        dropProbabilities.TryGetValue(item.name, out double probability);

                        var lootRecord = new LootDropDBRecord
                        {
                            CharacterPrefabGuid = guid,
                            ItemId = item.Id,
                            DropType = dropType,
                            DropIndex = i,
                            Probability = probability
                        };
                        lootDrops.Add(lootRecord);
                    }
                    else if (item != null && string.IsNullOrEmpty(item.Id))
                    {
                         Debug.LogWarning($"Skipping loot drop entry for item '{item.name}' in LootTable on character GUID '{guid}' because item ID is missing.", item);
                    }
                }
            }
        }

        CollectLootDrops(lootTable.GuaranteeOneDrop, "Guaranteed");
        CollectLootDrops(lootTable.CommonDrop, "Common");
        CollectLootDrops(lootTable.UncommonDrop, "Uncommon");
        CollectLootDrops(lootTable.RareDrop, "Rare");
        CollectLootDrops(lootTable.LegendaryDrop, "Legendary");

        return lootDrops;
    }
}
