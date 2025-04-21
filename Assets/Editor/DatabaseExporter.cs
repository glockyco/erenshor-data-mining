using System;
using System.Collections.Generic;
using System.IO;
using SQLite;
using UnityEditor;
using UnityEngine;

public class DatabaseExporter
{
    public const string DB_PATH = "../Erenshor.sqlite";
    private readonly DatabaseManager _dbManager;
    private readonly CharacterExporter _characterExporter;
    private readonly LootDropExporter _lootDropExporter;
    private readonly ItemExporter _itemExporter;

    public DatabaseExporter()
    {
        _dbManager = new DatabaseManager();
        _characterExporter = new CharacterExporter();
        _lootDropExporter = new LootDropExporter();
        _itemExporter = new ItemExporter();
    }

    // Asynchronous version of ExportAllToDB
    public void ExportAllToDBAsync(DatabaseOperation.ProgressCallback progressCallback = null)
    {
        // Create a state object to track progress
        var state = new Dictionary<string, object>
        {
            { "stage", "init" },
            { "dbPath", Path.Combine(Application.dataPath, DB_PATH) },
            { "db", null },
            { "characterGuids", null },
            { "characterIndex", 0 },
            { "characterCount", 0 },
            { "lootDropsCount", 0 },
            { "items", null },
            { "itemIndex", 0 },
            { "itemCount", 0 },
            { "totalCharacters", 0 },
            { "totalItems", 0 },
            { "completed", false }
        };

        // Define the operations for each stage
        var stageOperations = new Dictionary<string, DatabaseManager.ExportOperation>
        {
            { "init", InitializeAllDB },
            { "prepare_characters", PrepareCharacters },
            { "export_characters", ExportCharactersBatch },
            { "export_loot_drops", ExportLootDropsBatch },
            { "prepare_items", PrepareItems },
            { "export_items", ExportItemsBatch }
        };

        // Start the asynchronous operation
        _dbManager.ExportAsync(state,
            (s, callback) => _dbManager.GenericExportAsyncUpdate(s, callback, stageOperations,
                "Exported {0[characterCount]} characters, {0[lootDropsCount]} loot drops, and {0[itemCount]} items"),
            progressCallback);
    }

    // Initialize the database for all exports
    private void InitializeAllDB(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Create tables for characters, items, and loot drops
        db.CreateTable<CharacterDBRecord>();
        db.CreateTable<ItemDBRecord>();
        db.CreateTable<LootDropDBRecord>();

        // Clear existing records
        db.DeleteAll<CharacterDBRecord>();
        db.DeleteAll<ItemDBRecord>();
        db.DeleteAll<LootDropDBRecord>();

        state["stage"] = "prepare_characters";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.05f, "Database initialized");
    }

    // Prepare character data for export
    private void PrepareCharacters(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Find all character prefabs
        string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CharacterExporter.CHARACTERS_PATH });
        state["characterGuids"] = guids;
        state["totalCharacters"] = guids.Length;

        state["stage"] = "export_characters";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.1f, $"Found {guids.Length} character prefabs");
    }

    // Export a batch of characters
    private void ExportCharactersBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        string[] characterGuids = (string[])state["characterGuids"];
        int characterIndex = (int)state["characterIndex"];
        int characterCount = (int)state["characterCount"];
        int totalCharacters = (int)state["totalCharacters"];

        // Process a batch of characters
        int batchSize = 25;
        int endIndex = Math.Min(characterIndex + batchSize, characterGuids.Length);

        // Use a transaction for better performance
        db.BeginTransaction();

        try
        {
            // Create a list to hold records for bulk insert
            var records = new List<CharacterDBRecord>();

            for (int i = characterIndex; i < endIndex; i++)
            {
                string guid = characterGuids[i];
                string assetPath = AssetDatabase.GUIDToAssetPath(guid);
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);

                if (prefab != null)
                {
                    // Export character
                    CharacterDBRecord record = _characterExporter.ExportCharacter(prefab, guid);
                    if (record != null)
                    {
                        records.Add(record);
                    }
                }
            }

            // Bulk insert all records at once
            foreach (var record in records)
            {
                db.InsertOrReplace(record);
            }

            characterCount += records.Count;

            // Commit the transaction
            db.Commit();
        }
        catch (Exception ex)
        {
            // Rollback on error
            db.Rollback();
            Debug.LogError($"Error exporting characters: {ex.Message}");
        }

        // Update state
        state["characterIndex"] = endIndex;
        state["characterCount"] = characterCount;

        // Calculate progress (characters are 30% of the total progress)
        float progress = 0.1f + (0.2f * endIndex / totalCharacters);
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Exported {characterCount} characters ({endIndex}/{totalCharacters})");

        // Check if all characters have been processed
        if (endIndex >= characterGuids.Length)
        {
            // Reset character index for loot drops export
            state["characterIndex"] = 0;
            // Move to the next stage
            state["stage"] = "export_loot_drops";
        }
    }
    
        // Export a batch of loot drops
    private void ExportLootDropsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        string[] characterGuids = (string[])state["characterGuids"];
        int characterIndex = (int)state["characterIndex"];
        int lootDropsCount = (int)state["lootDropsCount"];
        int totalCharacters = (int)state["totalCharacters"];

        // Process a batch of characters
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
                        var lootDrops = _lootDropExporter.CollectLootDropsForCharacter(guid, lootTable);
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

        // Calculate progress (loot drops are 20% of the total progress)
        float progress = 0.3f + (0.2f * endIndex / totalCharacters);
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Exported {lootDropsCount} loot drops ({endIndex}/{totalCharacters} characters processed)");

        // Check if all characters have been processed
        if (endIndex >= characterGuids.Length)
        {
            // Move to the next stage
            state["stage"] = "prepare_items";
        }
    }

    // Prepare items data for export
    private void PrepareItems(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Load all Item assets
        Item[] items = Resources.LoadAll<Item>(ItemExporter.ITEMS_PATH);
        state["items"] = items;
        state["totalItems"] = items.Length;

        state["stage"] = "export_items";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.5f, $"Found {items.Length} items");
    }

    // Export a batch of items
    private void ExportItemsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        Item[] allItems = (Item[])state["items"];
        int itemIndex = (int)state["itemIndex"];
        int itemCount = (int)state["itemCount"];
        int totalItems = (int)state["totalItems"];

        // Process a larger batch of items for better performance
        int batchSize = 50;
        int endIndex = Math.Min(itemIndex + batchSize, allItems.Length);

        // Use a transaction for better performance
        db.BeginTransaction();

        try
        {
            // Create a list to hold records for bulk insert
            var records = new List<ItemDBRecord>();

            for (int i = itemIndex; i < endIndex; i++)
            {
                Item item = allItems[i];
                ItemDBRecord record = _itemExporter.ExportItem(item);
                records.Add(record);
            }

            // Bulk insert all records at once
            foreach (var record in records)
            {
                db.Insert(record);
            }

            itemCount += records.Count;

            // Commit the transaction
            db.Commit();
        }
        catch (Exception ex)
        {
            // Rollback on error
            db.Rollback();
            Debug.LogError($"Error exporting items: {ex.Message}");
        }

        // Update state
        state["itemIndex"] = endIndex;
        state["itemCount"] = itemCount;

        // Calculate progress (items are 30% of the total progress)
        float progress = 0.7f + (0.3f * endIndex / totalItems);
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Exported {itemCount} items ({endIndex}/{totalItems})");

        // Check if all items have been processed
        if (endIndex >= allItems.Length)
        {
            // Mark the operation as completed
            state["completed"] = true;
        }
    }

    // Convenience method to cancel any export operation
    public static void CancelExport()
    {
        DatabaseOperation.CancelOperation();
    }
}

