using System;
using System.Collections.Generic;
using System.IO;
using SQLite;
using UnityEditor;
using UnityEngine;
using UnityEditor.SceneManagement; // Needed for original scene path

public class DatabaseExporter
{
    public const string DB_PATH = "../Erenshor.sqlite";
    private readonly DatabaseManager _dbManager;
    private readonly CharacterExporter _characterExporter;
    private readonly LootDropExporter _lootDropExporter;
    private readonly ItemExporter _itemExporter;
    private readonly SpawnPointExporter _spawnPointExporter; // <-- Add SpawnPointExporter instance

    public DatabaseExporter()
    {
        _dbManager = new DatabaseManager();
        _characterExporter = new CharacterExporter();
        _lootDropExporter = new LootDropExporter();
        _itemExporter = new ItemExporter();
        _spawnPointExporter = new SpawnPointExporter(); // <-- Instantiate it
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
            // Character state
            { "characterGuids", null },
            { "characterIndex", 0 },
            { "characterCount", 0 },
            { "totalCharacters", 0 },
            // Loot drop state (uses characterGuids/Index/totalCharacters)
            { "lootDropsCount", 0 },
            // Spawn point state
            { "scenePaths", null },
            { "sceneIndex", 0 },
            { "spawnPointCount", 0 },
            { "spawnLinkCount", 0 },
            { "totalScenes", 0 },
            { "originalScenePath", EditorSceneManager.GetActiveScene().path }, // Store original scene path
            // Item state
            { "items", null },
            { "itemIndex", 0 },
            { "recordCount", 0 }, // Item records (including quality variants)
            { "totalBaseItems", 0 },
            // General state
            { "completed", false },
            { "progressCallback", progressCallback } // Store the callback
        };

        // Define the operations for each stage
        var stageOperations = new Dictionary<string, DatabaseManager.ExportOperation>
        {
            { "init", InitializeAllDB },
            { "prepare_characters", PrepareCharacters },
            { "export_characters", ExportCharactersBatch },
            { "export_loot_drops", ExportLootDropsBatch },
            { "prepare_scenes", PrepareScenes },           // <-- Add scene preparation stage
            { "export_spawn_points", ExportSpawnPointsBatch }, // <-- Add spawn point export stage
            { "prepare_items", PrepareItems },
            { "export_items", ExportItemsBatch }
        };

        // Start the asynchronous operation
        _dbManager.ExportAsync(state,
            (s, callback) => _dbManager.GenericExportAsyncUpdate(s, callback, stageOperations,
                "Exported {0[characterCount]} chars, {0[lootDropsCount]} loot drops, {0[spawnPointCount]} spawn points, {0[spawnLinkCount]} spawn links, {0[recordCount]} item records"), // <-- Updated message
            progressCallback);
    }

    // Initialize the database for all exports
    private void InitializeAllDB(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Create tables for characters, items, and loot drops
        // Create tables for characters, items, and loot drops
        db.CreateTable<CharacterDBRecord>();
        db.CreateTable<ItemDBRecord>();
        db.CreateTable<LootDropDBRecord>();
        db.CreateTable<SpawnPointDBRecord>();      // <-- Create SpawnPoints table
        db.CreateTable<SpawnPointCharacterDBRecord>(); // <-- Create SpawnPointCharacters table

        // Clear existing records
        db.DeleteAll<CharacterDBRecord>();
        db.DeleteAll<ItemDBRecord>();
        db.DeleteAll<LootDropDBRecord>();
        db.DeleteAll<SpawnPointDBRecord>();      // <-- Clear SpawnPoints table
        db.DeleteAll<SpawnPointCharacterDBRecord>(); // <-- Clear SpawnPointCharacters table

        state["stage"] = "prepare_characters";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        // Adjust progress slightly for the added steps
        callback?.Invoke(0.02f, "Database initialized");
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
        // Progress: 0.02 (init) + 0.03 = 0.05
        callback?.Invoke(0.05f, $"Found {guids.Length} character prefabs");
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

        // Progress: 0.05 (prev) + 0.20 (chars) = 0.25
        float progress = 0.05f + (0.20f * (totalCharacters > 0 ? (float)endIndex / totalCharacters : 1.0f));
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Exported {characterCount} characters ({endIndex}/{totalCharacters})");

        if (endIndex >= totalCharacters)
        {
            state["characterIndex"] = 0; // Reset for loot drops
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

        // Progress: 0.25 (prev) + 0.15 (loot) = 0.40
        float progress = 0.25f + (0.15f * (totalCharacters > 0 ? (float)endIndex / totalCharacters : 1.0f));
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Exported {lootDropsCount} loot drops ({endIndex}/{totalCharacters} characters processed)");

        if (endIndex >= totalCharacters)
        {
            state["stage"] = "prepare_scenes"; // <-- Move to prepare scenes next
        }
    }

    // Prepare scenes data for export (using SpawnPointExporter's logic)
    private void PrepareScenes(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Delegate to the SpawnPointExporter's preparation method
        // Note: This doesn't use the 'db' connection, just modifies state
        _spawnPointExporter.PrepareScenes(null, state); // Pass null for db as it's not needed here

        // Progress: 0.40 (prev) + 0.03 (prep scenes) = 0.43
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.43f, $"Found {(int)state["totalScenes"]} scenes");

        // State stage is already set to "export_spawn_points" by PrepareScenes
    }

    // Export a batch of spawn points (using SpawnPointExporter's logic)
    private void ExportSpawnPointsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Delegate the core logic to SpawnPointExporter's batch method
        // It will handle scene loading/unloading and transaction within the scene
        _spawnPointExporter.ExportSpawnPointsBatch(db, state);

        // Progress calculation is handled within _spawnPointExporter.ExportSpawnPointsBatch
        // We just need to update the overall progress range.
        // Spawn points take up 27% of progress (0.43 to 0.70)
        int sceneIndex = (int)state["sceneIndex"];
        int totalScenes = (int)state["totalScenes"];
        float spawnProgress = (totalScenes > 0 ? (float)sceneIndex / totalScenes : 1.0f);
        float overallProgress = 0.43f + (0.27f * spawnProgress);

        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(overallProgress, $"Processed {sceneIndex}/{totalScenes} scenes ({state["spawnPointCount"]} points, {state["spawnLinkCount"]} links)");


        // Check if the delegated method marked completion
        if ((bool)state["completed"])
        {
            state["completed"] = false; // Reset completion flag for the next stage
            state["stage"] = "prepare_items"; // Move to the next stage
             // Ensure final spawn point progress is reported at 0.70
            callback?.Invoke(0.70f, $"Finished exporting spawn points");
        }
        // If not completed, the GenericExportAsyncUpdate loop will call this method again
    }


    // Prepare items data for export
    private void PrepareItems(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Load all Item assets
        Item[] items = Resources.LoadAll<Item>(ItemExporter.ITEMS_PATH);
        state["items"] = items;
        state["totalBaseItems"] = items.Length; // Store base item count

        state["stage"] = "export_items";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        // Progress: 0.70 (prev) + 0.05 (prep items) = 0.75
        callback?.Invoke(0.75f, $"Found {items.Length} base items");
    }

    // Export a batch of items
    // Export a batch of items, including quality variants
    private void ExportItemsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        Item[] allItems = (Item[])state["items"];
        int itemIndex = (int)state["itemIndex"];
        int recordCount = (int)state["recordCount"]; // Renamed from itemCount
        int totalBaseItems = (int)state["totalBaseItems"]; // Renamed from totalItems

        // Process a batch of base items
        int batchSize = 20; // Match ItemExporter batch size
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

                // Determine if this item type should have quality variants
                bool hasQualityVariants = item.RequiredSlot != Item.SlotType.General &&
                                          item.Aura == null &&
                                          item.TeachSpell == null &&
                                          item.TeachSkill == null &&
                                          !item.Template;

                int maxQuality = hasQualityVariants ? 3 : 1;

                for (int quality = 1; quality <= maxQuality; quality++)
                {
                    // Skip invalid base items (missing ID)
                    if (string.IsNullOrEmpty(item.Id))
                    {
                        // Warning already logged by ItemExporter, just skip here
                        continue;
                    }
                    // Use the ItemExporter's helper method which now handles quality
                    ItemDBRecord record = _itemExporter.ExportItem(item, quality);
                    records.Add(record);
                }
            }

            // Bulk insert all records generated in this batch
            foreach (var record in records)
            {
                // Use InsertOrReplace in case an item ID somehow gets duplicated (though it shouldn't with quality suffix)
                db.InsertOrReplace(record);
            }

            recordCount += records.Count; // Update record count

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
        state["itemIndex"] = endIndex; // Progress based on base items processed
        state["recordCount"] = recordCount; // Update total records inserted

        // Progress: 0.75 (prev) + 0.25 (items) = 1.00
        float progress = 0.75f + (0.25f * (totalBaseItems > 0 ? (float)endIndex / totalBaseItems : 1.0f));
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Processed {endIndex}/{totalBaseItems} base items ({recordCount} item records exported)");

        if (endIndex >= totalBaseItems)
        {
            state["completed"] = true; // Mark the overall operation as completed
            // Restore original scene just in case something went wrong during spawn export cleanup
             string originalScenePath = state["originalScenePath"] as string;
             if (!string.IsNullOrEmpty(originalScenePath) && EditorSceneManager.GetActiveScene().path != originalScenePath)
             {
                 EditorSceneManager.OpenScene(originalScenePath);
             }
        }
    }

    // Convenience method to cancel any export operation
    public static void CancelExport()
    {
        DatabaseOperation.CancelOperation();
    }
}

