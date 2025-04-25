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
    private readonly SpawnPointExporter _spawnPointExporter;
    private readonly SpellExporter _spellExporter;

    public DatabaseExporter()
    {
        _dbManager = new DatabaseManager();
        _characterExporter = new CharacterExporter();
        _lootDropExporter = new LootDropExporter();
        _itemExporter = new ItemExporter();
        _spawnPointExporter = new SpawnPointExporter();
        _spellExporter = new SpellExporter();
    }

    // Asynchronous version of ExportAllToDB
    public void ExportAllToDBAsync(DatabaseOperation.ProgressCallback progressCallback = null)
    {
        // Recalculate progress allocation:
        // Init: 0.02 (2%)
        // Chars: 0.18 (18%) -> Prep 0.02, Export 0.16
        // Loot: 0.10 (10%) -> Export 0.10 (uses char prep)
        // Spawns: 0.25 (25%) -> Prep 0.02, Export 0.23
        // Items: 0.20 (20%) -> Prep 0.02, Export 0.18
        // Spells: 0.25 (25%) -> Prep 0.02, Export 0.23
        // Total: 1.00 (100%)

        var state = new Dictionary<string, object>
        {
            { "stage", "init" },
            { "dbPath", Path.Combine(Application.dataPath, DB_PATH) },
            { "db", null },
            // Character state
            { "characterGuids", null }, { "characterIndex", 0 }, { "characterCount", 0 }, { "totalCharacters", 0 },
            // Loot drop state
            { "lootDropsCount", 0 },
            // Spawn point state
            { "scenePaths", null }, { "sceneIndex", 0 }, { "spawnPointCount", 0 }, { "spawnLinkCount", 0 }, { "totalScenes", 0 },
            { "originalScenePath", EditorSceneManager.GetActiveScene().path },
            // Item state
            { "items", null }, { "itemIndex", 0 }, { "recordCount", 0 }, { "totalBaseItems", 0 },
            // Spell state
            { "spells", null }, { "spellIndex", 0 }, { "spellCount", 0 }, { "totalSpells", 0 },
            // General state
            { "completed", false },
            { "progressCallback", progressCallback }
        };

        // Define the operations for each stage
        var stageOperations = new Dictionary<string, DatabaseManager.ExportOperation>
        {
            { "init", InitializeAllDB },
            { "prepare_characters", PrepareCharacters },
            { "export_characters", ExportCharactersBatch },
            { "export_loot_drops", ExportLootDropsBatch },
            { "prepare_scenes", PrepareScenes },
            { "export_spawn_points", ExportSpawnPointsBatch },
            { "prepare_items", PrepareItems },
            { "export_items", ExportItemsBatch },
            { "prepare_spells", PrepareSpells },
            { "export_spells", ExportSpellsBatch }
        };

        _dbManager.ExportAsync(state,
            (s, callback) => _dbManager.GenericExportAsyncUpdate(s, callback, stageOperations,
                "Exported {0[characterCount]} chars, {0[lootDropsCount]} loot drops, {0[spawnPointCount]} spawns, {0[spawnLinkCount]} links, {0[recordCount]} items, {0[spellCount]} spells"),
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
        db.CreateTable<SpawnPointDBRecord>();
        db.CreateTable<SpawnPointCharacterDBRecord>();
        db.CreateTable<SpellDBRecord>();

        // Clear existing records
        db.DeleteAll<CharacterDBRecord>();
        db.DeleteAll<ItemDBRecord>();
        db.DeleteAll<LootDropDBRecord>();
        db.DeleteAll<SpawnPointDBRecord>();
        db.DeleteAll<SpawnPointCharacterDBRecord>();
        db.DeleteAll<SpellDBRecord>();

        state["stage"] = "prepare_characters";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.02f, "Database initialized"); // Progress: 0.02
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
        // Progress: 0.02 (init) + 0.02 (prep chars) = 0.04
        callback?.Invoke(0.04f, $"Found {guids.Length} character prefabs");
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

        // Progress: 0.04 (prev) + 0.16 (chars export) = 0.20
        float progress = 0.04f + (0.16f * (totalCharacters > 0 ? (float)endIndex / totalCharacters : 1.0f));
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Exported {characterCount} characters ({endIndex}/{totalCharacters})");

        if (endIndex >= totalCharacters)
        {
            state["characterIndex"] = 0; // Reset for loot drops
            state["stage"] = "export_loot_drops";
             // Ensure final char progress is reported at 0.20
            callback?.Invoke(0.20f, $"Finished exporting characters");
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

        // Progress: 0.20 (prev) + 0.10 (loot) = 0.30
        float progress = 0.20f + (0.10f * (totalCharacters > 0 ? (float)endIndex / totalCharacters : 1.0f));
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Exported {lootDropsCount} loot drops ({endIndex}/{totalCharacters} characters processed)");

        if (endIndex >= totalCharacters)
        {
            state["stage"] = "prepare_scenes";
             // Ensure final loot progress is reported at 0.30
            callback?.Invoke(0.30f, $"Finished exporting loot drops");
        }
    }

    // Prepare scenes data for export
    private void PrepareScenes(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Delegate to the SpawnPointExporter's preparation method
        // Note: This doesn't use the 'db' connection, just modifies state
        _spawnPointExporter.PrepareScenes(null, state);

        // Progress: 0.30 (prev) + 0.02 (prep scenes) = 0.32
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.32f, $"Found {(int)state["totalScenes"]} scenes");
        // Stage is set by PrepareScenes
    }

    // Export a batch of spawn points
    private void ExportSpawnPointsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Delegate the core logic to SpawnPointExporter's batch method
        // It will handle scene loading/unloading and transaction within the scene
        _spawnPointExporter.ExportSpawnPointsBatch(db, state);

        // Progress calculation is handled within _spawnPointExporter.ExportSpawnPointsBatch
        // We just need to update the overall progress range.
        // Progress: 0.32 (prev) + 0.23 (spawns export) = 0.55
        int sceneIndex = (int)state["sceneIndex"];
        int totalScenes = (int)state["totalScenes"];
        float spawnProgress = (totalScenes > 0 ? (float)sceneIndex / totalScenes : 1.0f);
        float overallProgress = 0.32f + (0.23f * spawnProgress);

        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(overallProgress, $"Processed {sceneIndex}/{totalScenes} scenes ({state["spawnPointCount"]} points, {state["spawnLinkCount"]} links)");
        if ((bool)state["completed"])
        {
            state["completed"] = false;
            state["stage"] = "prepare_items";
             // Ensure final spawn progress is reported at 0.55
            callback?.Invoke(0.55f, $"Finished exporting spawn points");
        }
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
        // Progress: 0.55 (prev) + 0.02 (prep items) = 0.57
        callback?.Invoke(0.57f, $"Found {items.Length} base items");
    }

    // Export a batch of items
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
                    ItemDBRecord record = _itemExporter.ExportItem(item, quality, i);
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
        state["itemIndex"] = endIndex;
        state["recordCount"] = recordCount;

        // Progress: 0.57 (prev) + 0.18 (items export) = 0.75
        float progress = 0.57f + (0.18f * (totalBaseItems > 0 ? (float)endIndex / totalBaseItems : 1.0f));
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Processed {endIndex}/{totalBaseItems} base items ({recordCount} item records exported)");

        if (endIndex >= totalBaseItems)
        {
            // Don't mark completed yet, move to spells
            state["stage"] = "prepare_spells";
             // Ensure final item progress is reported at 0.75
            callback?.Invoke(0.75f, $"Finished exporting items");

            // Restore original scene if needed (moved here from the end of item export)
             string originalScenePath = state["originalScenePath"] as string;
             if (!string.IsNullOrEmpty(originalScenePath) && EditorSceneManager.GetActiveScene().path != originalScenePath)
             {
                 EditorSceneManager.OpenScene(originalScenePath);
             }
        }
    }

    // Prepare spells data for export
    private void PrepareSpells(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Delegate to SpellExporter's preparation method
        _spellExporter.PrepareSpells(db, state); // db isn't used by PrepareSpells, but pass for consistency

        // Progress: 0.75 (prev) + 0.02 (prep spells) = 0.77
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.77f, $"Found {(int)state["totalSpells"]} valid spells");
        // Stage is set by PrepareSpells
    }

    // Export a batch of spells
    private void ExportSpellsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Delegate to SpellExporter's batch method
        _spellExporter.ExportSpellsBatch(db, state);

        // Progress: 0.77 (prev) + 0.23 (spells export) = 1.00
        int spellIndex = (int)state["spellIndex"];
        int totalSpells = (int)state["totalSpells"];
        float spellProgress = (totalSpells > 0 ? (float)spellIndex / totalSpells : 1.0f);
        float overallProgress = 0.77f + (0.23f * spellProgress);

        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(overallProgress, $"Exported {state["spellCount"]}/{totalSpells} spells");

        // Check if the delegated method marked completion
        if ((bool)state["completed"])
        {
            // This is now the final stage, so let GenericExportAsyncUpdate handle completion
             // Ensure final spell progress is reported at 1.00
            callback?.Invoke(1.00f, $"Finished exporting spells");
        }
        // If not completed, GenericExportAsyncUpdate loop will call this method again
    }


    // Convenience method to cancel any export operation
    public static void CancelExport()
    {
        DatabaseOperation.CancelOperation();
    }
}

