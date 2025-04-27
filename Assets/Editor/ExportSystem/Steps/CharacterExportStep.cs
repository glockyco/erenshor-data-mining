using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEditor;
using UnityEngine;

public class CharacterExportStep : IExportStep
{
    public const string CHARACTERS_PATH = "Assets/GameObject";

    // --- Metadata ---
    public string StepName => "Characters";

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(CharacterDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        reportProgress(0, 0);

        // --- Data Fetching ---
        string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
        int totalAssets = guids.Length;

        if (totalAssets == 0)
        {
            reportProgress(0, 0);
            Debug.LogWarning("No character prefabs found.");
            return;
        }

        reportProgress(0, totalAssets);
        await Task.Yield();

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
                        foreach (var rec in batchRecords)
                        {
                            db.InsertOrReplace(rec);
                        }
                    });
                    recordCount += batchRecords.Count;
                    batchRecords.Clear();
                }
                catch (Exception ex)
                {
                    Debug.LogError($"Error inserting character batch (around index {i}): {ex.Message}");
                    reportProgress(processedCount, totalAssets); // Report progress before throwing
                    throw;
                }

                // --- Progress Reporting ---
                reportProgress(processedCount, totalAssets);
                await Task.Yield();
            }
        }
        
        reportProgress(processedCount, totalAssets);
        Debug.Log($"Finished exporting {recordCount} characters from {processedCount} prefabs.");
    }

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
