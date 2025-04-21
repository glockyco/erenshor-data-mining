using System;
using System.Collections.Generic;
using System.IO;
using SQLite;
using UnityEditor;
using UnityEngine;

public class CharacterExporter
{
    public const string CHARACTERS_PATH = "Assets/GameObject";
    private readonly DatabaseManager _dbManager;

    public CharacterExporter()
    {
        _dbManager = new DatabaseManager();
    }

    // Asynchronous version of ExportCharactersToDB
    public void ExportCharactersToDBAsync(DatabaseOperation.ProgressCallback progressCallback = null)
    {
        // Create a state object to track progress
        var state = new Dictionary<string, object>
        {
            { "stage", "init" },
            { "dbPath", Path.Combine(Application.dataPath, DatabaseOperation.DB_PATH) },
            { "db", null },
            { "characterGuids", null },
            { "characterIndex", 0 },
            { "characterCount", 0 },
            { "totalCharacters", 0 },
            { "completed", false }
        };

        // Define the operations for each stage
        var stageOperations = new Dictionary<string, DatabaseManager.ExportOperation>
        {
            { "init", InitializeCharactersDB },
            { "prepare_characters", PrepareCharacters },
            { "export_characters", ExportCharactersBatch }
        };

        // Start the asynchronous operation
        _dbManager.ExportAsync(state,
            (s, callback) => _dbManager.GenericExportAsyncUpdate(s, callback, stageOperations, "Exported {0[characterCount]} characters"),
            progressCallback);
    }

    // Initialize the database for characters export
    private void InitializeCharactersDB(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Create tables for characters only
        db.CreateTable<CharacterDBRecord>();

        // Clear existing character records
        db.DeleteAll<CharacterDBRecord>();

        state["stage"] = "prepare_characters";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.1f, "Database initialized");
    }

    // Prepare character data for export
    private void PrepareCharacters(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Find all character prefabs
        string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
        state["characterGuids"] = guids;
        state["totalCharacters"] = guids.Length;

        state["stage"] = "export_characters";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.2f, $"Found {guids.Length} character prefabs");
    }

    // Export a batch of characters
    private void ExportCharactersBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        string[] characterGuids = (string[])state["characterGuids"];
        int characterIndex = (int)state["characterIndex"];
        int characterCount = (int)state["characterCount"];
        int totalCharacters = (int)state["totalCharacters"];

        // Process a larger batch of characters for better performance
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
                    CharacterDBRecord record = ExportCharacter(prefab, guid);
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

        // Calculate progress
        float progress = 0.2f + (0.8f * endIndex / totalCharacters);
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Exported {characterCount} characters ({endIndex}/{totalCharacters})");

        // Check if all characters have been processed
        if (endIndex >= characterGuids.Length)
        {
            // Mark the operation as completed
            state["completed"] = true;
        }
    }

    // Helper method to export a character to the database
    public CharacterDBRecord ExportCharacter(GameObject prefab, string guid)
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
}
