using System;
using System.Collections.Generic;
using System.IO;
using SQLite;
using UnityEditor;
using UnityEngine;

public class LootDropExporter
{
    public const string CHARACTERS_PATH = "Assets/GameObject";
    private readonly DatabaseManager _dbManager;

    public LootDropExporter()
    {
        _dbManager = new DatabaseManager();
    }

    // Asynchronous version of ExportLootDropsToDB
    public void ExportLootDropsToDBAsync(DatabaseOperation.ProgressCallback progressCallback = null)
    {
        // Create a state object to track progress
        var state = new Dictionary<string, object>
        {
            { "stage", "init" },
            { "dbPath", Path.Combine(Application.dataPath, DatabaseOperation.DB_PATH) },
            { "db", null },
            { "characterGuids", null },
            { "characterIndex", 0 },
            { "lootDropsCount", 0 },
            { "totalCharacters", 0 },
            { "completed", false }
        };

        // Define the operations for each stage
        var stageOperations = new Dictionary<string, DatabaseManager.ExportOperation>
        {
            { "init", InitializeLootDropsDB },
            { "prepare_characters", PrepareCharacters },
            { "export_loot_drops", ExportLootDropsBatch }
        };

        // Start the asynchronous operation
        _dbManager.ExportAsync(state,
            (s, callback) => _dbManager.GenericExportAsyncUpdate(s, callback, stageOperations, "Exported {0[lootDropsCount]} loot drops"),
            progressCallback);
    }

    // Initialize the database for loot drops export
    private void InitializeLootDropsDB(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Create tables for loot drops
        db.CreateTable<LootDropDBRecord>();

        // Clear existing loot drop records
        db.DeleteAll<LootDropDBRecord>();

        state["stage"] = "prepare_characters";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.1f, "Database initialized");
    }

    // Prepare character data for loot drop export
    private void PrepareCharacters(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Find all character prefabs
        string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
        state["characterGuids"] = guids;
        state["totalCharacters"] = guids.Length;

        state["stage"] = "export_loot_drops";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.2f, $"Found {guids.Length} character prefabs");
    }

    // Export a batch of loot drops
    private void ExportLootDropsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        string[] characterGuids = (string[])state["characterGuids"];
        int characterIndex = (int)state["characterIndex"];
        int lootDropsCount = (int)state["lootDropsCount"];
        int totalCharacters = (int)state["totalCharacters"];

        // Process a larger batch of characters for better performance
        int batchSize = 25;
        int endIndex = Math.Min(characterIndex + batchSize, characterGuids.Length);

        // Use a transaction for better performance
        db.BeginTransaction();

        try
        {
            // Create a list to hold all loot drop records for bulk insert
            var allLootDrops = new List<LootDropDBRecord>();

            for (int i = characterIndex; i < endIndex; i++)
            {
                string guid = characterGuids[i];
                string assetPath = AssetDatabase.GUIDToAssetPath(guid);
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);

                if (prefab != null)
                {
                    // Check if the prefab has a LootTable component and export loot drop data
                    LootTable lootTable = prefab.GetComponent<LootTable>();
                    if (lootTable != null)
                    {
                        // Collect loot drops instead of inserting them one by one
                        var lootDrops = CollectLootDropsForCharacter(guid, lootTable);
                        allLootDrops.AddRange(lootDrops);
                    }
                }
            }

            // Bulk insert all loot drops at once
            foreach (var lootDrop in allLootDrops)
            {
                db.Insert(lootDrop);
            }

            lootDropsCount += allLootDrops.Count;

            // Commit the transaction
            db.Commit();
        }
        catch (Exception ex)
        {
            // Rollback on error
            db.Rollback();
            Debug.LogError($"Error exporting loot drops: {ex.Message}");
        }

        // Update state
        state["characterIndex"] = endIndex;
        state["lootDropsCount"] = lootDropsCount;

        // Calculate progress
        float progress = 0.2f + (0.8f * endIndex / totalCharacters);
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Exported {lootDropsCount} loot drops ({endIndex}/{totalCharacters} characters processed)");

        // Check if all characters have been processed
        if (endIndex >= characterGuids.Length)
        {
            // Mark the operation as completed
            state["completed"] = true;
        }
    }

    // Collect loot drops for a character without inserting them directly
    public List<LootDropDBRecord> CollectLootDropsForCharacter(string guid, LootTable lootTable)
    {
        var lootDrops = new List<LootDropDBRecord>();

        // Helper method to collect a specific type of loot drops
        void CollectLootDrops(List<Item> items, string dropType)
        {
            if (items != null)
            {
                for (int i = 0; i < items.Count; i++)
                {
                    Item item = items[i];
                    if (item != null)
                    {
                        var lootRecord = new LootDropDBRecord
                        {
                            CharacterPrefabGuid = guid,
                            ItemId = item.Id,
                            DropType = dropType,
                            DropIndex = i
                        };
                        lootDrops.Add(lootRecord);
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
