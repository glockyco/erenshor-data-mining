using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEngine;

public class QuestExportStep : IExportStep
{
    public const string QUESTS_PATH = "Quests"; // Path within Resources folder (matches QuestDB)

    // --- Metadata ---
    public string StepName => "Quests";

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(QuestDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        reportProgress(0, 0);

        // --- Data Fetching ---
        Quest[] quests = Resources.LoadAll<Quest>(QUESTS_PATH);
        
        // Filter out quests without a DBName, as it's the primary key
        var validQuests = quests.Where(q => q != null && !string.IsNullOrEmpty(q.DBName)).ToArray();
        int skippedCount = quests.Length - validQuests.Length;
        if (skippedCount > 0)
        {
            Debug.LogWarning($"Skipped {skippedCount} quest(s) that were null or had missing DBName.");
        }

        int totalQuests = validQuests.Length;

        if (totalQuests == 0)
        {
            reportProgress(0, 0);
            Debug.LogWarning("No valid quest assets found.");
            return;
        }

        reportProgress(0, totalQuests);
        await Task.Yield();

        // --- Processing & DB Interaction ---
        int batchSize = 50;
        var batchRecords = new List<QuestDBRecord>();
        int processedCount = 0;
        int recordCount = 0;

        for (int i = 0; i < totalQuests; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            Quest quest = validQuests[i];

            // --- Extraction Logic ---
            QuestDBRecord record = ExportQuest(quest, i);
            if (record != null)
            {
                batchRecords.Add(record);
            }

            processedCount++;

            // --- Batch Insertion ---
            if (batchRecords.Count >= batchSize || (processedCount == totalQuests && batchRecords.Count > 0))
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
                    Debug.LogError($"Error inserting quest batch (around index {i}): {ex.Message}");
                    reportProgress(processedCount, totalQuests);
                    throw;
                }

                // --- Progress Reporting ---
                reportProgress(processedCount, totalQuests);
                await Task.Yield();
            }
        }
        
        reportProgress(processedCount, totalQuests);
        Debug.Log($"Finished exporting {recordCount} quests from {processedCount} valid assets.");
    }

    private QuestDBRecord ExportQuest(Quest quest, int questDbIndex)
    {
        if (quest == null || string.IsNullOrEmpty(quest.DBName)) return null;

        string requiredItems = quest.RequiredItems != null
            ? string.Join(", ", quest.RequiredItems.Where(item => item != null && !string.IsNullOrEmpty(item.Id)).Select(item => item.Id))
            : "";

        string affectedFactions = quest.AffectFactions != null
            ? string.Join(", ", quest.AffectFactions.Where(f => f != null && !string.IsNullOrEmpty(f.REFNAME)).Select(f => f.REFNAME))
            : "";

        string affectedFactionAmounts = quest.AffectFactionAmts != null
            ? string.Join(", ", quest.AffectFactionAmts)
            : "";

        string completeQuests = quest.CompleteOtherQuests != null
            ? string.Join(", ", quest.CompleteOtherQuests.Where(q => q != null && !string.IsNullOrEmpty(q.DBName)).Select(q => q.DBName))
            : "";

        return new QuestDBRecord
        {
            // --- Core Identification ---
            QuestDBIndex = questDbIndex,
            QuestName = quest.QuestName,
            QuestDesc = quest.QuestDesc,

            // --- Requirements ---
            RequiredItemIds = requiredItems,

            // --- Rewards & Completion ---
            XPonComplete = quest.XPonComplete,
            ItemOnCompleteId = quest.ItemOnComplete?.Id,
            GoldOnComplete = quest.GoldOnComplete,
            AssignNewQuestOnCompleteDBName = quest.AssignNewQuestOnComplete?.DBName,
            CompleteOtherQuestDBNames = completeQuests,

            // --- Dialog & Text ---
            DialogOnSuccess = quest.DialogOnSuccess,
            DialogOnPartialSuccess = quest.DialogOnPartialSuccess,
            DisableText = quest.DisableText,

            // --- Faction Adjustments ---
            AffectedFactions = affectedFactions,
            AffectedFactionAmounts = affectedFactionAmounts,

            // --- Flags & Behavior ---
            AssignThisQuestOnPartialComplete = quest.AssignThisQuestOnPartialComplete,
            Repeatable = quest.repeatable,
            DisableQuest = quest.DisableQuest,
            KillTurnInHolder = quest.KillTurnInHolder,
            DestroyTurnInHolder = quest.DestroyTurnInHolder,
            DropInvulnOnHolder = quest.DropInvulnOnHolder,
            OncePerSpawnInstance = quest.OncePerSpawnInstance,

            // --- Achievements ---
            SetAchievementOnGet = quest.SetAchievementOnGet,
            SetAchievementOnFinish = quest.SetAchievementOnFinish,

            // --- Internals / Metadata ---
            DBName = quest.DBName,
            ResourceName = quest.name,
        };
    }
}
