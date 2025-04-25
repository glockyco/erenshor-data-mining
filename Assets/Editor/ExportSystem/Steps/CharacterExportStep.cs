using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEditor;
using UnityEngine;

public class CharacterExportStep : IExportStep
{
    public const string CHARACTERS_PATH = "Assets/GameObject"; // Path relative to Assets

    // --- Metadata ---
    public string StepName => "Characters";
    public float ProgressWeight => 1.8f; // Adjusted weight

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(CharacterDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, IProgressReporter reporter, CancellationToken cancellationToken)
    {
        reporter.Report(0f, "Finding character prefabs...");

        // --- Data Fetching (Unity API) ---
        string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
        int totalAssets = guids.Length;

        if (totalAssets == 0)
        {
            reporter.Report(1f, "No character prefabs found.");
            return;
        }

        reporter.Report(0.05f, $"Found {totalAssets} prefabs. Exporting...");
        await Task.Yield(); // Allow UI update

        // --- Processing & DB Interaction ---
        int batchSize = 25;
        var batchRecords = new List<CharacterDBRecord>();
        int processedCount = 0;
        int recordCount = 0;

        for (int i = 0; i < totalAssets; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            string guid = guids[i];
            string assetPath = AssetDatabase.GUIDToAssetPath(guid);
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);

            if (prefab != null)
            {
                CharacterDBRecord record = ExportCharacter(prefab, guid); // Use helper
                if (record != null)
                {
                    batchRecords.Add(record);
                }
            }

            processedCount++;

            // --- Batch Insertion ---
            if (batchRecords.Count >= batchSize || (processedCount == totalAssets && batchRecords.Count > 0))
            {
                try
                {
                    db.RunInTransaction(() =>
                    {
                        // Call InsertOrReplace for each record individually within the transaction
                        foreach (var record in batchRecords)
                        {
                            db.InsertOrReplace(record); // Use InsertOrReplace based on CharacterDBRecord PK
                        }
                    });
                    recordCount += batchRecords.Count;
                    batchRecords.Clear();
                }
                catch (Exception ex)
                {
                    Debug.LogError($"Error inserting character batch (around index {i}): {ex.Message}");
                    reporter.Report((float)processedCount / totalAssets, $"Error inserting batch: {ex.Message}");
                    throw;
                }

                // --- Progress Reporting (After batch) ---
                float progress = (float)processedCount / totalAssets;
                reporter.Report(progress, $"Exported {recordCount} characters ({processedCount}/{totalAssets} prefabs)...");
                await Task.Yield();
            }
            else if (processedCount == totalAssets)
            {
                 reporter.Report(1.0f, $"Exported {recordCount} characters ({processedCount}/{totalAssets} prefabs)...");
            }
        }
    }

    // Helper method to export a character (Adapted from CharacterExporter)
    private CharacterDBRecord ExportCharacter(GameObject prefab, string guid)
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
