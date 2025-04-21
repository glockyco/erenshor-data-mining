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

    public static void ExportAllToDB()
    {
        string dbPath = Path.Combine(Application.dataPath, DB_PATH);
        var db = new SQLiteConnection(dbPath);

        // Create tables for all types
        db.CreateTable<CharacterDBRecord>();
        db.CreateTable<ItemDBRecord>();
        db.CreateTable<LootDropDBRecord>();

        // Clear existing records
        db.DeleteAll<CharacterDBRecord>();
        db.DeleteAll<ItemDBRecord>();
        db.DeleteAll<LootDropDBRecord>();

        // Export all types
        int characterCount = ExportCharacters(db, true);
        int itemCount = ExportItems(db);

        Debug.Log($"Exported {characterCount} characters and {itemCount} items to SQLite database at {dbPath}");
    }

    // Asynchronous version of ExportAllToDB
    public static void ExportAllToDBAsync(ProgressCallback progressCallback = null)
    {
        ResetCancelFlag();

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

        // Start the asynchronous operation
        EditorApplication.update += () => ExportAllToDBAsyncUpdate(state, progressCallback);
    }

    private static void ExportAllToDBAsyncUpdate(Dictionary<string, object> state, ProgressCallback progressCallback)
    {
        // Check if the operation has been cancelled
        if (_cancelRequested)
        {
            progressCallback?.Invoke(1.0f, "Export cancelled");
            EditorApplication.update -= () => ExportAllToDBAsyncUpdate(state, progressCallback);
            ResetCancelFlag();
            return;
        }

        // Check if the operation has completed
        if ((bool)state["completed"])
        {
            int characterCount = (int)state["characterCount"];
            int itemCount = (int)state["itemCount"];
            string dbPath = (string)state["dbPath"];

            progressCallback?.Invoke(1.0f, $"Exported {characterCount} characters and {itemCount} items");
            Debug.Log($"Exported {characterCount} characters and {itemCount} items to SQLite database at {dbPath}");

            EditorApplication.update -= () => ExportAllToDBAsyncUpdate(state, progressCallback);
            return;
        }

        // Declare db variable at the method level
        SQLiteConnection db;
        string stage = (string)state["stage"];

        switch (stage)
        {
            case "init":
                // Initialize the database
                string dbPath = (string)state["dbPath"];
                db = new SQLiteConnection(dbPath);
                state["db"] = db;

                // Create tables for all types
                db.CreateTable<CharacterDBRecord>();
                db.CreateTable<ItemDBRecord>();
                db.CreateTable<LootDropDBRecord>();

                // Clear existing records
                db.DeleteAll<CharacterDBRecord>();
                db.DeleteAll<ItemDBRecord>();
                db.DeleteAll<LootDropDBRecord>();

                progressCallback?.Invoke(0.05f, "Database initialized");

                // Move to the next stage
                state["stage"] = "prepare_characters";
                break;

            case "prepare_characters":
                // Find all character prefabs
                string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
                state["characterGuids"] = guids;
                state["totalCharacters"] = guids.Length;

                progressCallback?.Invoke(0.1f, $"Found {guids.Length} character prefabs");

                // Move to the next stage
                state["stage"] = "export_characters";
                break;

            case "export_characters":
                db = (SQLiteConnection)state["db"];
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
                        Character character = prefab.GetComponent<Character>();
                        if (character != null)
                        {
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

                            db.InsertOrReplace(record);
                            characterCount++;

                            // Export loot drops
                            LootTable lootTable = prefab.GetComponent<LootTable>();
                            if (lootTable != null)
                            {
                                // Export guaranteed drops
                                if (lootTable.GuaranteeOneDrop != null)
                                {
                                    for (int j = 0; j < lootTable.GuaranteeOneDrop.Count; j++)
                                    {
                                        Item item = lootTable.GuaranteeOneDrop[j];
                                        if (item != null)
                                        {
                                            var lootRecord = new LootDropDBRecord
                                            {
                                                CharacterPrefabGuid = guid,
                                                ItemId = item.Id,
                                                DropType = "Guaranteed",
                                                DropIndex = j
                                            };
                                            db.Insert(lootRecord);
                                            lootDropsCount++;
                                        }
                                    }
                                }

                                // Export common drops
                                if (lootTable.CommonDrop != null)
                                {
                                    for (int j = 0; j < lootTable.CommonDrop.Count; j++)
                                    {
                                        Item item = lootTable.CommonDrop[j];
                                        if (item != null)
                                        {
                                            var lootRecord = new LootDropDBRecord
                                            {
                                                CharacterPrefabGuid = guid,
                                                ItemId = item.Id,
                                                DropType = "Common",
                                                DropIndex = j
                                            };
                                            db.Insert(lootRecord);
                                            lootDropsCount++;
                                        }
                                    }
                                }

                                // Export uncommon drops
                                if (lootTable.UncommonDrop != null)
                                {
                                    for (int j = 0; j < lootTable.UncommonDrop.Count; j++)
                                    {
                                        Item item = lootTable.UncommonDrop[j];
                                        if (item != null)
                                        {
                                            var lootRecord = new LootDropDBRecord
                                            {
                                                CharacterPrefabGuid = guid,
                                                ItemId = item.Id,
                                                DropType = "Uncommon",
                                                DropIndex = j
                                            };
                                            db.Insert(lootRecord);
                                            lootDropsCount++;
                                        }
                                    }
                                }

                                // Export rare drops
                                if (lootTable.RareDrop != null)
                                {
                                    for (int j = 0; j < lootTable.RareDrop.Count; j++)
                                    {
                                        Item item = lootTable.RareDrop[j];
                                        if (item != null)
                                        {
                                            var lootRecord = new LootDropDBRecord
                                            {
                                                CharacterPrefabGuid = guid,
                                                ItemId = item.Id,
                                                DropType = "Rare",
                                                DropIndex = j
                                            };
                                            db.Insert(lootRecord);
                                            lootDropsCount++;
                                        }
                                    }
                                }

                                // Export legendary drops
                                if (lootTable.LegendaryDrop != null)
                                {
                                    for (int j = 0; j < lootTable.LegendaryDrop.Count; j++)
                                    {
                                        Item item = lootTable.LegendaryDrop[j];
                                        if (item != null)
                                        {
                                            var lootRecord = new LootDropDBRecord
                                            {
                                                CharacterPrefabGuid = guid,
                                                ItemId = item.Id,
                                                DropType = "Legendary",
                                                DropIndex = j
                                            };
                                            db.Insert(lootRecord);
                                            lootDropsCount++;
                                        }
                                    }
                                }
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
                progressCallback?.Invoke(progress, $"Exported {characterCount} characters ({endIndex}/{totalCharacters})");

                // Check if all characters have been processed
                if (endIndex >= characterGuids.Length)
                {
                    // Move to the next stage
                    state["stage"] = "prepare_items";
                }
                break;

            case "prepare_items":
                // Load all Item assets
                Item[] items = Resources.LoadAll<Item>(ITEMS_PATH);
                state["items"] = items;
                state["totalItems"] = items.Length;

                progressCallback?.Invoke(0.5f, $"Found {items.Length} items");

                // Move to the next stage
                state["stage"] = "export_items";
                break;

            case "export_items":
                db = (SQLiteConnection)state["db"];
                Item[] allItems = (Item[])state["items"];
                int itemIndex = (int)state["itemIndex"];
                int itemCount = (int)state["itemCount"];
                int totalItems = (int)state["totalItems"];

                // Process a batch of items (adjust batch size as needed)
                batchSize = 10;
                endIndex = Math.Min(itemIndex + batchSize, allItems.Length);

                for (int i = itemIndex; i < endIndex; i++)
                {
                    Item item = allItems[i];

                    var record = new ItemDBRecord
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

                    db.Insert(record);
                    itemCount++;
                }

                // Update state
                state["itemIndex"] = endIndex;
                state["itemCount"] = itemCount;

                // Calculate progress (items are the remaining 50% of the total progress)
                progress = 0.5f + (0.5f * endIndex / totalItems);
                progressCallback?.Invoke(progress, $"Exported {itemCount} items ({endIndex}/{totalItems})");

                // Check if all items have been processed
                if (endIndex >= allItems.Length)
                {
                    // Mark the operation as completed
                    state["completed"] = true;
                }
                break;
        }
    }

    public static void ExportCharactersToDB()
    {
        string dbPath = Path.Combine(Application.dataPath, DB_PATH);
        var db = new SQLiteConnection(dbPath);

        // Create tables for characters
        db.CreateTable<CharacterDBRecord>();

        // Clear existing character records
        db.DeleteAll<CharacterDBRecord>();

        // Export characters
        int characterCount = ExportCharacters(db, false);

        Debug.Log($"Exported {characterCount} characters to SQLite database at {dbPath}");
    }

    public static void ExportLootDropsToDB()
    {
        string dbPath = Path.Combine(Application.dataPath, DB_PATH);
        var db = new SQLiteConnection(dbPath);

        // Create tables for loot drops
        db.CreateTable<LootDropDBRecord>();

        // Clear existing loot drop records
        db.DeleteAll<LootDropDBRecord>();

        // Export loot drops
        int lootDropsCount = ExportLootDrops(db);

        Debug.Log($"Exported {lootDropsCount} loot drops to SQLite database at {dbPath}");
    }

    // Asynchronous version of ExportLootDropsToDB
    public static void ExportLootDropsToDBAsync(ProgressCallback progressCallback = null)
    {
        ResetCancelFlag();

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

        // Start the asynchronous operation
        EditorApplication.update += () => ExportLootDropsToDBAsyncUpdate(state, progressCallback);
    }

    private static void ExportLootDropsToDBAsyncUpdate(Dictionary<string, object> state, ProgressCallback progressCallback)
    {
        // Check if the operation has been cancelled
        if (_cancelRequested)
        {
            progressCallback?.Invoke(1.0f, "Export cancelled");
            EditorApplication.update -= () => ExportLootDropsToDBAsyncUpdate(state, progressCallback);
            ResetCancelFlag();
            return;
        }

        // Check if the operation has completed
        if ((bool)state["completed"])
        {
            int lootDropsCount = (int)state["lootDropsCount"];
            string dbPath = (string)state["dbPath"];

            progressCallback?.Invoke(1.0f, $"Exported {lootDropsCount} loot drops");
            Debug.Log($"Exported {lootDropsCount} loot drops to SQLite database at {dbPath}");

            EditorApplication.update -= () => ExportLootDropsToDBAsyncUpdate(state, progressCallback);
            return;
        }

        // Declare db variable at the method level
        SQLiteConnection db;
        string stage = (string)state["stage"];

        switch (stage)
        {
            case "init":
                // Initialize the database
                string dbPath = (string)state["dbPath"];
                db = new SQLiteConnection(dbPath);
                state["db"] = db;

                // Create tables for loot drops
                db.CreateTable<LootDropDBRecord>();

                // Clear existing loot drop records
                db.DeleteAll<LootDropDBRecord>();

                progressCallback?.Invoke(0.1f, "Database initialized");

                // Move to the next stage
                state["stage"] = "prepare_characters";
                break;

            case "prepare_characters":
                // Find all character prefabs
                string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
                state["characterGuids"] = guids;
                state["totalCharacters"] = guids.Length;

                progressCallback?.Invoke(0.2f, $"Found {guids.Length} character prefabs");

                // Move to the next stage
                state["stage"] = "export_loot_drops";
                break;

            case "export_loot_drops":
                db = (SQLiteConnection)state["db"];
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
                progressCallback?.Invoke(progress, $"Exported {lootDropsCount} loot drops ({endIndex}/{totalCharacters} characters processed)");

                // Check if all characters have been processed
                if (endIndex >= characterGuids.Length)
                {
                    // Mark the operation as completed
                    state["completed"] = true;
                }
                break;
        }
    }

    // Asynchronous version of ExportCharactersToDB
    public static void ExportCharactersToDBAsync(ProgressCallback progressCallback = null)
    {
        ResetCancelFlag();

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
            { "totalCharacters", 0 },
            { "completed", false }
        };

        // Start the asynchronous operation
        EditorApplication.update += () => ExportCharactersToDBAsyncUpdate(state, progressCallback);
    }

    private static void ExportCharactersToDBAsyncUpdate(Dictionary<string, object> state, ProgressCallback progressCallback)
    {
        // Check if the operation has been cancelled
        if (_cancelRequested)
        {
            progressCallback?.Invoke(1.0f, "Export cancelled");
            EditorApplication.update -= () => ExportCharactersToDBAsyncUpdate(state, progressCallback);
            ResetCancelFlag();
            return;
        }

        // Check if the operation has completed
        if ((bool)state["completed"])
        {
            int characterCount = (int)state["characterCount"];
            string dbPath = (string)state["dbPath"];

            progressCallback?.Invoke(1.0f, $"Exported {characterCount} characters");
            Debug.Log($"Exported {characterCount} characters to SQLite database at {dbPath}");

            EditorApplication.update -= () => ExportCharactersToDBAsyncUpdate(state, progressCallback);
            return;
        }

        // Declare db variable at the method level
        SQLiteConnection db;
        string stage = (string)state["stage"];

        switch (stage)
        {
            case "init":
                // Initialize the database
                string dbPath = (string)state["dbPath"];
                db = new SQLiteConnection(dbPath);
                state["db"] = db;

                // Create tables for characters only
                db.CreateTable<CharacterDBRecord>();

                // Clear existing character records
                db.DeleteAll<CharacterDBRecord>();

                progressCallback?.Invoke(0.1f, "Database initialized");

                // Move to the next stage
                state["stage"] = "prepare_characters";
                break;

            case "prepare_characters":
                // Find all character prefabs
                string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
                state["characterGuids"] = guids;
                state["totalCharacters"] = guids.Length;

                progressCallback?.Invoke(0.2f, $"Found {guids.Length} character prefabs");

                // Move to the next stage
                state["stage"] = "export_characters";
                break;

            case "export_characters":
                db = (SQLiteConnection)state["db"];
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
                        Character character = prefab.GetComponent<Character>();
                        if (character != null)
                        {
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
                progressCallback?.Invoke(progress, $"Exported {characterCount} characters ({endIndex}/{totalCharacters})");

                // Check if all characters have been processed
                if (endIndex >= characterGuids.Length)
                {
                    // Mark the operation as completed
                    state["completed"] = true;
                }
                break;
        }
    }

    public static void ExportItemsToDB()
    {
        string dbPath = Path.Combine(Application.dataPath, DB_PATH);
        var db = new SQLiteConnection(dbPath);

        // Create table for items
        db.CreateTable<ItemDBRecord>();

        // Clear existing item records
        db.DeleteAll<ItemDBRecord>();

        // Export items
        int itemCount = ExportItems(db);

        Debug.Log($"Exported {itemCount} items to SQLite database at {dbPath}");
    }

    // Asynchronous version of ExportItemsToDB
    public static void ExportItemsToDBAsync(ProgressCallback progressCallback = null)
    {
        ResetCancelFlag();

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

        // Start the asynchronous operation
        EditorApplication.update += () => ExportItemsToDBAsyncUpdate(state, progressCallback);
    }

    private static void ExportItemsToDBAsyncUpdate(Dictionary<string, object> state, ProgressCallback progressCallback)
    {
        // Check if the operation has been cancelled
        if (_cancelRequested)
        {
            progressCallback?.Invoke(1.0f, "Export cancelled");
            EditorApplication.update -= () => ExportItemsToDBAsyncUpdate(state, progressCallback);
            ResetCancelFlag();
            return;
        }

        // Check if the operation has completed
        if ((bool)state["completed"])
        {
            int itemCount = (int)state["itemCount"];
            string dbPath = (string)state["dbPath"];

            progressCallback?.Invoke(1.0f, $"Exported {itemCount} items");
            Debug.Log($"Exported {itemCount} items to SQLite database at {dbPath}");

            EditorApplication.update -= () => ExportItemsToDBAsyncUpdate(state, progressCallback);
            return;
        }

        // Declare db variable at the method level
        SQLiteConnection db;
        string stage = (string)state["stage"];

        switch (stage)
        {
            case "init":
                // Initialize the database
                string dbPath = (string)state["dbPath"];
                db = new SQLiteConnection(dbPath);
                state["db"] = db;

                // Create table for items
                db.CreateTable<ItemDBRecord>();

                // Clear existing item records
                db.DeleteAll<ItemDBRecord>();

                progressCallback?.Invoke(0.1f, "Database initialized");

                // Move to the next stage
                state["stage"] = "prepare_items";
                break;

            case "prepare_items":
                // Load all Item assets
                Item[] items = Resources.LoadAll<Item>(ITEMS_PATH);
                state["items"] = items;
                state["totalItems"] = items.Length;

                progressCallback?.Invoke(0.2f, $"Found {items.Length} items");

                // Move to the next stage
                state["stage"] = "export_items";
                break;

            case "export_items":
                db = (SQLiteConnection)state["db"];
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

                    var record = new ItemDBRecord
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

                    db.Insert(record);
                    itemCount++;
                }

                // Update state
                state["itemIndex"] = endIndex;
                state["itemCount"] = itemCount;

                // Calculate progress
                float progress = 0.2f + (0.8f * endIndex / totalItems);
                progressCallback?.Invoke(progress, $"Exported {itemCount} items ({endIndex}/{totalItems})");

                // Check if all items have been processed
                if (endIndex >= allItems.Length)
                {
                    // Mark the operation as completed
                    state["completed"] = true;
                }
                break;
        }
    }

    private static int ExportCharacters(SQLiteConnection db, bool includeLootDrops = true)
    {
        string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
        if (guids == null || guids.Length == 0)
        {
            Debug.LogWarning($"No prefabs found in {CHARACTERS_PATH}!");
            return 0;
        }

        int exportedCount = 0;
        int lootDropsCount = 0;

        foreach (string guid in guids)
        {
            string assetPath = AssetDatabase.GUIDToAssetPath(guid);
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
            if (prefab == null)
                continue;

            Character character = prefab.GetComponent<Character>();
            if (character == null)
                continue;

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

            // Check if the prefab has a Stats component and include stats data if available
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

            db.InsertOrReplace(record);
            exportedCount++;

            // Check if the prefab has a LootTable component and export loot drop data if includeLootDrops is true
            if (includeLootDrops)
            {
                LootTable lootTable = prefab.GetComponent<LootTable>();
                if (lootTable != null)
                {
                    lootDropsCount += ExportLootDropsForCharacter(db, guid, lootTable);
                }
            }
        }

        if (includeLootDrops)
        {
            Debug.Log($"Exported {lootDropsCount} loot drops for characters");
        }
        return exportedCount;
    }

    private static int ExportLootDrops(SQLiteConnection db)
    {
        string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
        if (guids == null || guids.Length == 0)
        {
            Debug.LogWarning($"No prefabs found in {CHARACTERS_PATH}!");
            return 0;
        }

        int lootDropsCount = 0;

        foreach (string guid in guids)
        {
            string assetPath = AssetDatabase.GUIDToAssetPath(guid);
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
            if (prefab == null)
                continue;

            // Check if the prefab has a LootTable component and export loot drop data
            LootTable lootTable = prefab.GetComponent<LootTable>();
            if (lootTable != null)
            {
                lootDropsCount += ExportLootDropsForCharacter(db, guid, lootTable);
            }
        }

        return lootDropsCount;
    }

    private static int ExportLootDropsForCharacter(SQLiteConnection db, string guid, LootTable lootTable)
    {
        int lootDropsCount = 0;

        // Export guaranteed drops
        if (lootTable.GuaranteeOneDrop != null)
        {
            for (int i = 0; i < lootTable.GuaranteeOneDrop.Count; i++)
            {
                Item item = lootTable.GuaranteeOneDrop[i];
                if (item != null)
                {
                    var lootRecord = new LootDropDBRecord
                    {
                        CharacterPrefabGuid = guid,
                        ItemId = item.Id,
                        DropType = "Guaranteed",
                        DropIndex = i
                    };
                    db.Insert(lootRecord);
                    lootDropsCount++;
                }
            }
        }

        // Export common drops
        if (lootTable.CommonDrop != null)
        {
            for (int i = 0; i < lootTable.CommonDrop.Count; i++)
            {
                Item item = lootTable.CommonDrop[i];
                if (item != null)
                {
                    var lootRecord = new LootDropDBRecord
                    {
                        CharacterPrefabGuid = guid,
                        ItemId = item.Id,
                        DropType = "Common",
                        DropIndex = i
                    };
                    db.Insert(lootRecord);
                    lootDropsCount++;
                }
            }
        }

        // Export uncommon drops
        if (lootTable.UncommonDrop != null)
        {
            for (int i = 0; i < lootTable.UncommonDrop.Count; i++)
            {
                Item item = lootTable.UncommonDrop[i];
                if (item != null)
                {
                    var lootRecord = new LootDropDBRecord
                    {
                        CharacterPrefabGuid = guid,
                        ItemId = item.Id,
                        DropType = "Uncommon",
                        DropIndex = i
                    };
                    db.Insert(lootRecord);
                    lootDropsCount++;
                }
            }
        }

        // Export rare drops
        if (lootTable.RareDrop != null)
        {
            for (int i = 0; i < lootTable.RareDrop.Count; i++)
            {
                Item item = lootTable.RareDrop[i];
                if (item != null)
                {
                    var lootRecord = new LootDropDBRecord
                    {
                        CharacterPrefabGuid = guid,
                        ItemId = item.Id,
                        DropType = "Rare",
                        DropIndex = i
                    };
                    db.Insert(lootRecord);
                    lootDropsCount++;
                }
            }
        }

        // Export legendary drops
        if (lootTable.LegendaryDrop != null)
        {
            for (int i = 0; i < lootTable.LegendaryDrop.Count; i++)
            {
                Item item = lootTable.LegendaryDrop[i];
                if (item != null)
                {
                    var lootRecord = new LootDropDBRecord
                    {
                        CharacterPrefabGuid = guid,
                        ItemId = item.Id,
                        DropType = "Legendary",
                        DropIndex = i
                    };
                    db.Insert(lootRecord);
                    lootDropsCount++;
                }
            }
        }

        return lootDropsCount;
    }

    private static int ExportItems(SQLiteConnection db)
    {
        // Load all Item assets from Resources/items
        Item[] items = Resources.LoadAll<Item>(ITEMS_PATH);
        if (items == null || items.Length == 0)
        {
            Debug.LogWarning($"No items found in Resources/{ITEMS_PATH}!");
            return 0;
        }

        int exportedCount = 0;

        foreach (var item in items)
        {
            var record = new ItemDBRecord
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

            db.Insert(record);
            exportedCount++;
        }

        return exportedCount;
    }
}
