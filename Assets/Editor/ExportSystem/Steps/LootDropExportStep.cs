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
    // Dependency - passed in constructor
    private readonly LootTableProbabilityCalculator _probabilityCalculator;

    // Constants
    public const string CHARACTERS_PATH = "Assets/GameObject"; // Path relative to Assets

    // Constructor to receive dependencies
    public LootDropExportStep(LootTableProbabilityCalculator probabilityCalculator)
    {
        _probabilityCalculator = probabilityCalculator ?? throw new ArgumentNullException(nameof(probabilityCalculator));
    }

    // --- Metadata ---
    public string StepName => "Loot Drops";
    public float ProgressWeight => 1.0f;

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(LootDropDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, IProgressReporter reporter, CancellationToken cancellationToken)
    {
        reporter.Report(0f, "Finding character prefabs for loot tables...");

        // --- Data Fetching (Character Prefabs) ---
        string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
        // Filter immediately for those with LootTable components
        var characterPrefabs = guids
            .Select(guid =>
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                return (prefab, guid);
            })
            .Where(item => item.prefab != null && item.prefab.GetComponent<LootTable>() != null)
            .ToList(); // ToList to get a count

        int totalCharacters = characterPrefabs.Count;

        if (totalCharacters == 0)
        {
            reporter.Report(1f, "No character prefabs with LootTable found.");
            return;
        }

        reporter.Report(0.05f, $"Found {totalCharacters} characters with loot tables. Exporting drops...");
        await Task.Yield();

        // --- Processing & DB Interaction ---
        int batchSize = 50; // Records per batch
        var batchRecords = new List<LootDropDBRecord>();
        int processedCount = 0;
        int totalRecordCount = 0;

        foreach (var (prefab, guid) in characterPrefabs)
        {
            cancellationToken.ThrowIfCancellationRequested();

            LootTable lootTable = prefab.GetComponent<LootTable>(); // Already checked, but get it again
            if (lootTable != null) // Should always be true here
            {
                // --- Extraction Logic (Using helper) ---
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
                        // Use Insert, assuming LootDropDBRecord has appropriate PK or no conflicts expected per batch
                        db.InsertAll(batchRecords);
                    });
                    totalRecordCount += batchRecords.Count;
                    batchRecords.Clear();
                }
                catch (Exception ex)
                {
                    Debug.LogError($"Error inserting loot drop batch (around character index {processedCount - 1}): {ex.Message}");
                    reporter.Report((float)processedCount / totalCharacters, $"Error inserting batch: {ex.Message}");
                    throw;
                }

                // --- Progress Reporting ---
                float progress = (float)processedCount / totalCharacters;
                reporter.Report(progress, $"Exported {totalRecordCount} loot drops ({processedCount}/{totalCharacters} characters)...");
                await Task.Yield();
            }
             else if (processedCount == totalCharacters)
            {
                 reporter.Report(1.0f, $"Exported {totalRecordCount} loot drops ({processedCount}/{totalCharacters} characters)...");
            }
        }
    }

    // Helper method to collect loot drops (Adapted from LootDropExporter)
    private List<LootDropDBRecord> CollectLootDropsForCharacter(string guid, LootTable lootTable)
    {
        var lootDrops = new List<LootDropDBRecord>();

        // Calculate drop probabilities using the injected calculator
        Dictionary<string, double> dropProbabilities = _probabilityCalculator.CalculateDropProbabilities(lootTable);

        // Helper method to collect a specific type of loot drops
        void CollectLootDrops(List<Item> items, string dropType)
        {
            if (items != null)
            {
                for (int i = 0; i < items.Count; i++)
                {
                    Item item = items[i];
                    if (item != null && !string.IsNullOrEmpty(item.Id)) // Ensure item and its ID are valid
                    {
                        // Get the probability for this item
                        dropProbabilities.TryGetValue(item.name, out double probability); // Default 0.0 if not found

                        var lootRecord = new LootDropDBRecord
                        {
                            CharacterPrefabGuid = guid,
                            ItemId = item.Id, // Use Item's unique ID
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

        // Collect all types of drops
        CollectLootDrops(lootTable.GuaranteeOneDrop, "Guaranteed");
        CollectLootDrops(lootTable.CommonDrop, "Common");
        CollectLootDrops(lootTable.UncommonDrop, "Uncommon");
        CollectLootDrops(lootTable.RareDrop, "Rare");
        CollectLootDrops(lootTable.LegendaryDrop, "Legendary");

        return lootDrops;
    }
}
