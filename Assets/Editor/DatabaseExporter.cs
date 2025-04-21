using System;
using System.IO;
using System.Collections.Generic;
using SQLite;
using UnityEditor;
using UnityEngine;

public class DatabaseExporter
{
    public const string DB_PATH = "../Erenshor.sqlite";
    private const string ITEMS_PATH = "items";
    private const string CHARACTERS_PATH = "Assets/GameObject";

    // Delegate for progress reporting
    public delegate void ProgressCallback(float progress, string status);

    // Flag to cancel ongoing operations
    private static bool _cancelRequested = false;

    // Method to request cancellation of ongoing operations
    public static void CancelExport()
    {
        _cancelRequested = true;
    }

    // Method to reset cancellation flag
    private static void ResetCancelFlag()
    {
        _cancelRequested = false;
    }

    // Delegate for export operations
    private delegate void ExportOperation(SQLiteConnection db, Dictionary<string, object> state);

    // Generic async export method
    private static void ExportAsync(
        Dictionary<string, object> initialState,
        Action<Dictionary<string, object>, ProgressCallback> updateMethod,
        ProgressCallback progressCallback = null
    ) {
        ResetCancelFlag();

        // Store the progress callback in the state
        initialState["progressCallback"] = progressCallback;

        // Start the asynchronous operation
        EditorApplication.update += () => updateMethod(initialState, progressCallback);
    }

    // Generic async update method
    private static void GenericExportAsyncUpdate(
        Dictionary<string, object> state,
        ProgressCallback progressCallback,
        Dictionary<string, ExportOperation> stageOperations,
        string completionMessage
    ) {
        // Check if the operation has been cancelled
        if (_cancelRequested)
        {
            progressCallback?.Invoke(1.0f, "Export cancelled");
            EditorApplication.update -= () => GenericExportAsyncUpdate(state, progressCallback, stageOperations, completionMessage);
            ResetCancelFlag();
            return;
        }

        // Check if the operation has completed
        if ((bool)state["completed"])
        {
            string dbPath = (string)state["dbPath"];
            string message = string.Format(completionMessage, state);

            progressCallback?.Invoke(1.0f, message);
            Debug.Log($"{message} to SQLite database at {dbPath}");

            EditorApplication.update -= () => GenericExportAsyncUpdate(state, progressCallback, stageOperations, completionMessage);
            return;
        }

        // Get the current stage and execute the corresponding operation
        string stage = (string)state["stage"];
        if (stageOperations.TryGetValue(stage, out ExportOperation operation))
        {
            SQLiteConnection db = state["db"] as SQLiteConnection;
            if (db == null && stage == "init")
            {
                // Initialize the database
                string dbPath = (string)state["dbPath"];
                db = new SQLiteConnection(dbPath);
                state["db"] = db;
            }

            // Execute the operation for the current stage
            operation(db, state);
        }
        else
        {
            Debug.LogError($"Unknown stage: {stage}");
            state["completed"] = true;
        }
    }

    // Asynchronous version of ExportAllToDB
    public static void ExportAllToDBAsync(ProgressCallback progressCallback = null)
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
        var stageOperations = new Dictionary<string, ExportOperation>
        {
            { "init", InitializeAllDB },
            { "prepare_characters", PrepareCharacters },
            { "export_characters", ExportCharactersAndLootDropsBatch },
            { "prepare_items", PrepareItems },
            { "export_items", ExportItemsBatch }
        };

        // Start the asynchronous operation
        ExportAsync(state, 
            (s, callback) => GenericExportAsyncUpdate(s, callback, stageOperations, 
                "Exported {0[characterCount]} characters and {0[itemCount]} items"), 
            progressCallback);
    }

    // Initialize the database for all exports
    private static void InitializeAllDB(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Create tables for all types
        db.CreateTable<CharacterDBRecord>();
        db.CreateTable<ItemDBRecord>();
        db.CreateTable<LootDropDBRecord>();

        // Clear existing records
        db.DeleteAll<CharacterDBRecord>();
        db.DeleteAll<ItemDBRecord>();
        db.DeleteAll<LootDropDBRecord>();

        state["stage"] = "prepare_characters";
        ProgressCallback callback = state["progressCallback"] as ProgressCallback;
        callback?.Invoke(0.05f, "Database initialized");
    }

    // Export a batch of characters and their loot drops
    private static void ExportCharactersAndLootDropsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        string[] characterGuids = (string[])state["characterGuids"];
        int characterIndex = (int)state["characterIndex"];
        int characterCount = (int)state["characterCount"];
        int lootDropsCount = (int)state["lootDropsCount"];
        int totalCharacters = (int)state["totalCharacters"];

        // Process a batch of characters (adjust batch size as needed)
        int batchSize = 5;
        int endIndex = Math.Min(characterIndex + batchSize, characterGuids.Length);

        for (int i = characterIndex; i < endIndex; i++)
        {
            string guid = characterGuids[i];
            string assetPath = AssetDatabase.GUIDToAssetPath(guid);
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);

            if (prefab != null)
            {
                // Export character
                CharacterDBRecord record = ExportCharacter(prefab, guid);
                if (record != null)
                {
                    db.InsertOrReplace(record);
                    characterCount++;

                    // Export loot drops
                    LootTable lootTable = prefab.GetComponent<LootTable>();
                    if (lootTable != null)
                    {
                        lootDropsCount += ExportLootDropsForCharacter(db, guid, lootTable);
                    }
                }
            }
        }

        // Update state
        state["characterIndex"] = endIndex;
        state["characterCount"] = characterCount;
        state["lootDropsCount"] = lootDropsCount;

        // Calculate progress (characters are 50% of the total progress)
        float progress = 0.1f + (0.4f * endIndex / totalCharacters);
        ProgressCallback callback = state["progressCallback"] as ProgressCallback;
        callback?.Invoke(progress, $"Exported {characterCount} characters ({endIndex}/{totalCharacters})");

        // Check if all characters have been processed
        if (endIndex >= characterGuids.Length)
        {
            // Move to the next stage
            state["stage"] = "prepare_items";
        }
    }



    // Asynchronous version of ExportLootDropsToDB
    public static void ExportLootDropsToDBAsync(ProgressCallback progressCallback = null)
    {
        // Create a state object to track progress
        var state = new Dictionary<string, object>
        {
            { "stage", "init" },
            { "dbPath", Path.Combine(Application.dataPath, DB_PATH) },
            { "db", null },
            { "characterGuids", null },
            { "characterIndex", 0 },
            { "lootDropsCount", 0 },
            { "totalCharacters", 0 },
            { "completed", false }
        };

        // Define the operations for each stage
        var stageOperations = new Dictionary<string, ExportOperation>
        {
            { "init", InitializeLootDropsDB },
            { "prepare_characters", PrepareCharacters },
            { "export_loot_drops", ExportLootDropsBatch }
        };

        // Start the asynchronous operation
        ExportAsync(state, 
            (s, callback) => GenericExportAsyncUpdate(s, callback, stageOperations, "Exported {0[lootDropsCount]} loot drops"), 
            progressCallback);
    }

    // Initialize the database for loot drops export
    private static void InitializeLootDropsDB(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Create tables for loot drops
        db.CreateTable<LootDropDBRecord>();

        // Clear existing loot drop records
        db.DeleteAll<LootDropDBRecord>();

        state["stage"] = "prepare_characters";
        ProgressCallback callback = state["progressCallback"] as ProgressCallback;
        callback?.Invoke(0.1f, "Database initialized");
    }

    // Export a batch of loot drops
    private static void ExportLootDropsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        string[] characterGuids = (string[])state["characterGuids"];
        int characterIndex = (int)state["characterIndex"];
        int lootDropsCount = (int)state["lootDropsCount"];
        int totalCharacters = (int)state["totalCharacters"];

        // Process a batch of characters (adjust batch size as needed)
        int batchSize = 5;
        int endIndex = Math.Min(characterIndex + batchSize, characterGuids.Length);

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
                    lootDropsCount += ExportLootDropsForCharacter(db, guid, lootTable);
                }
            }
        }

        // Update state
        state["characterIndex"] = endIndex;
        state["lootDropsCount"] = lootDropsCount;

        // Calculate progress
        float progress = 0.2f + (0.8f * endIndex / totalCharacters);
        ProgressCallback callback = state["progressCallback"] as ProgressCallback;
        callback?.Invoke(progress, $"Exported {lootDropsCount} loot drops ({endIndex}/{totalCharacters} characters processed)");

        // Check if all characters have been processed
        if (endIndex >= characterGuids.Length)
        {
            // Mark the operation as completed
            state["completed"] = true;
        }
    }

    // Asynchronous version of ExportCharactersToDB
    public static void ExportCharactersToDBAsync(ProgressCallback progressCallback = null)
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
            { "totalCharacters", 0 },
            { "completed", false }
        };

        // Define the operations for each stage
        var stageOperations = new Dictionary<string, ExportOperation>
        {
            { "init", InitializeCharactersDB },
            { "prepare_characters", PrepareCharacters },
            { "export_characters", ExportCharactersBatch }
        };

        // Start the asynchronous operation
        ExportAsync(state, 
            (s, callback) => GenericExportAsyncUpdate(s, callback, stageOperations, "Exported {0[characterCount]} characters"), 
            progressCallback);
    }

    // Initialize the database for characters export
    private static void InitializeCharactersDB(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Create tables for characters only
        db.CreateTable<CharacterDBRecord>();

        // Clear existing character records
        db.DeleteAll<CharacterDBRecord>();

        state["stage"] = "prepare_characters";
        ProgressCallback callback = state["progressCallback"] as ProgressCallback;
        callback?.Invoke(0.1f, "Database initialized");
    }

    // Prepare character data for export
    private static void PrepareCharacters(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Find all character prefabs
        string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
        state["characterGuids"] = guids;
        state["totalCharacters"] = guids.Length;

        state["stage"] = "export_characters";
        ProgressCallback callback = state["progressCallback"] as ProgressCallback;
        callback?.Invoke(0.2f, $"Found {guids.Length} character prefabs");
    }

    // Export a batch of characters
    private static void ExportCharactersBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        string[] characterGuids = (string[])state["characterGuids"];
        int characterIndex = (int)state["characterIndex"];
        int characterCount = (int)state["characterCount"];
        int totalCharacters = (int)state["totalCharacters"];

        // Process a batch of characters (adjust batch size as needed)
        int batchSize = 5;
        int endIndex = Math.Min(characterIndex + batchSize, characterGuids.Length);

        for (int i = characterIndex; i < endIndex; i++)
        {
            string guid = characterGuids[i];
            string assetPath = AssetDatabase.GUIDToAssetPath(guid);
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);

            if (prefab != null)
            {
                CharacterDBRecord record = ExportCharacter(prefab, guid);
                if (record != null)
                {
                    db.InsertOrReplace(record);
                    characterCount++;
                }
            }
        }

        // Update state
        state["characterIndex"] = endIndex;
        state["characterCount"] = characterCount;

        // Calculate progress
        float progress = 0.2f + (0.8f * endIndex / totalCharacters);
        ProgressCallback callback = state["progressCallback"] as ProgressCallback;
        callback?.Invoke(progress, $"Exported {characterCount} characters ({endIndex}/{totalCharacters})");

        // Check if all characters have been processed
        if (endIndex >= characterGuids.Length)
        {
            // Mark the operation as completed
            state["completed"] = true;
        }
    }


    // Asynchronous version of ExportItemsToDB
    public static void ExportItemsToDBAsync(ProgressCallback progressCallback = null)
    {
        // Create a state object to track progress
        var state = new Dictionary<string, object>
        {
            { "stage", "init" },
            { "dbPath", Path.Combine(Application.dataPath, DB_PATH) },
            { "db", null },
            { "items", null },
            { "itemIndex", 0 },
            { "itemCount", 0 },
            { "totalItems", 0 },
            { "completed", false }
        };

        // Define the operations for each stage
        var stageOperations = new Dictionary<string, ExportOperation>
        {
            { "init", InitializeItemsDB },
            { "prepare_items", PrepareItems },
            { "export_items", ExportItemsBatch }
        };

        // Start the asynchronous operation
        ExportAsync(state, 
            (s, callback) => GenericExportAsyncUpdate(s, callback, stageOperations, "Exported {0[itemCount]} items"), 
            progressCallback);
    }

    // Initialize the database for items export
    private static void InitializeItemsDB(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Create table for items
        db.CreateTable<ItemDBRecord>();

        // Clear existing item records
        db.DeleteAll<ItemDBRecord>();

        state["stage"] = "prepare_items";
        ProgressCallback callback = state["progressCallback"] as ProgressCallback;
        callback?.Invoke(0.1f, "Database initialized");
    }

    // Prepare items data for export
    private static void PrepareItems(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Load all Item assets
        Item[] items = Resources.LoadAll<Item>(ITEMS_PATH);
        state["items"] = items;
        state["totalItems"] = items.Length;

        state["stage"] = "export_items";
        ProgressCallback callback = state["progressCallback"] as ProgressCallback;
        callback?.Invoke(0.2f, $"Found {items.Length} items");
    }

    // Export a batch of items
    private static void ExportItemsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        Item[] allItems = (Item[])state["items"];
        int itemIndex = (int)state["itemIndex"];
        int itemCount = (int)state["itemCount"];
        int totalItems = (int)state["totalItems"];

        // Process a batch of items (adjust batch size as needed)
        int batchSize = 10;
        int endIndex = Math.Min(itemIndex + batchSize, allItems.Length);

        for (int i = itemIndex; i < endIndex; i++)
        {
            Item item = allItems[i];
            ItemDBRecord record = ExportItem(item);
            db.Insert(record);
            itemCount++;
        }

        // Update state
        state["itemIndex"] = endIndex;
        state["itemCount"] = itemCount;

        // Calculate progress
        float progress = 0.2f + (0.8f * endIndex / totalItems);
        ProgressCallback callback = state["progressCallback"] as ProgressCallback;
        callback?.Invoke(progress, $"Exported {itemCount} items ({endIndex}/{totalItems})");

        // Check if all items have been processed
        if (endIndex >= allItems.Length)
        {
            // Mark the operation as completed
            state["completed"] = true;
        }
    }



    // Helper method to export a character to the database
    private static CharacterDBRecord ExportCharacter(GameObject prefab, string guid)
    {
        Character character = prefab.GetComponent<Character>();
        if (character == null)
            return null;

        NPC npc = prefab.GetComponent<NPC>();

        var record = new CharacterDBRecord
        {
            PrefabGuid = guid,
            PrefabName = prefab.name,
            NPCName = npc != null ? npc.NPCName : string.Empty,
            MyFaction = (int)character.MyFaction,
            BaseFaction = (int)character.BaseFaction,
            TempFaction = (int)character.TempFaction,
            AggroRange = character.AggroRange,
            Alive = character.Alive,
            isNPC = character.isNPC,
            isVendor = character.isVendor,
            AttackRange = character.AttackRange,
            Invulnerable = character.Invulnerable,
        };

        // Check if the prefab has a Stats component
        Stats stats = prefab.GetComponent<Stats>();
        if (stats != null)
        {
            record.HasStats = true;
            record.CharacterName = stats.MyName;
            record.Level = stats.Level;
            record.BaseHP = stats.BaseHP;
            record.BaseAC = stats.BaseAC;
            record.BaseMana = stats.BaseMana;
            record.BaseStr = stats.BaseStr;
            record.BaseEnd = stats.BaseEnd;
            record.BaseDex = stats.BaseDex;
            record.BaseAgi = stats.BaseAgi;
            record.BaseInt = stats.BaseInt;
            record.BaseWis = stats.BaseWis;
            record.BaseCha = stats.BaseCha;
            record.BaseRes = stats.BaseRes;
            record.BaseMR = stats.BaseMR;
            record.BaseER = stats.BaseER;
            record.BasePR = stats.BasePR;
            record.BaseVR = stats.BaseVR;
        }

        return record;
    }

    // Helper method to export an item to the database
    private static ItemDBRecord ExportItem(Item item)
    {
        return new ItemDBRecord
        {
            Id = item.Id,
            ItemName = item.ItemName,
            ItemLevel = item.ItemLevel,
            HP = item.HP,
            AC = item.AC,
            Mana = item.Mana,
            WeaponDmg = item.WeaponDmg,
            WeaponDly = item.WeaponDly,
            Str = item.Str,
            End = item.End,
            Dex = item.Dex,
            Agi = item.Agi,
            Int = item.Int,
            Wis = item.Wis,
            Cha = item.Cha,
            Res = item.Res,
            MR = item.MR,
            ER = item.ER,
            PR = item.PR,
            VR = item.VR,
            RequiredSlot = (int)item.RequiredSlot,
            ThisWeaponType = (int)item.ThisWeaponType,
            ItemValue = item.ItemValue,
            Lore = item.Lore,
            Shield = item.Shield,
            WeaponProcChance = item.WeaponProcChance,
            SpellCastTime = item.SpellCastTime,
            HideHairWhenEquipped = item.HideHairWhenEquipped,
            HideHeadWhenEquipped = item.HideHeadWhenEquipped,
            Stackable = item.Stackable,
            Disposable = item.Disposable,
            Unique = item.Unique,
            Mining = item.Mining,
            FuelSource = item.FuelSource,
            Template = item.Template,
            SimPlayersCantGet = item.SimPlayersCantGet,
            FuelLevel = (int)item.FuelLevel,
            Relic = item.Relic,
            BookTitle = item.BookTitle
        };
    }

    private static int ExportLootDropsForCharacter(SQLiteConnection db, string guid, LootTable lootTable)
    {
        int lootDropsCount = 0;

        // Helper method to export a specific type of loot drops
        int ExportLootDrops(List<Item> items, string dropType)
        {
            int count = 0;
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
                        db.Insert(lootRecord);
                        count++;
                    }
                }
            }
            return count;
        }

        // Export all types of drops
        lootDropsCount += ExportLootDrops(lootTable.GuaranteeOneDrop, "Guaranteed");
        lootDropsCount += ExportLootDrops(lootTable.CommonDrop, "Common");
        lootDropsCount += ExportLootDrops(lootTable.UncommonDrop, "Uncommon");
        lootDropsCount += ExportLootDrops(lootTable.RareDrop, "Rare");
        lootDropsCount += ExportLootDrops(lootTable.LegendaryDrop, "Legendary");

        return lootDropsCount;
    }
}
