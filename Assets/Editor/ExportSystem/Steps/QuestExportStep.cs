using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEngine; // Required for Resources.LoadAll

public class QuestExportStep : IExportStep
{
    public const string QUESTS_PATH = "Quests"; // Path within Resources folder (matches QuestDB)

    // --- Metadata ---
    public string StepName => "Quests";
    public float ProgressWeight => 1.0f; // Adjust weight as needed

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(QuestDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, IProgressReporter reporter, CancellationToken cancellationToken)
    {
        reporter.Report(0f, "Loading quest assets...");

        // --- Data Fetching (Unity API - Resources.LoadAll) ---
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
            reporter.Report(1f, "No valid quest assets found.");
            return;
        }

        reporter.Report(0.05f, $"Found {totalQuests} valid quests. Exporting...");
        await Task.Yield();

        // --- Processing & DB Interaction ---
        int batchSize = 50; // Adjust batch size as needed
        var batchRecords = new List<QuestDBRecord>();
        int processedCount = 0;
        int recordCount = 0;

        for (int i = 0; i < totalQuests; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            Quest quest = validQuests[i];

            // --- Extraction Logic (Using helper) ---
            QuestDBRecord record = ExportQuest(quest, i);
            if (record != null) // Should generally not be null after filtering
            {
                batchRecords.Add(record);
            }

            processedCount++;

            // --- Batch Insertion ---
            if (batchRecords.Count >= batchSize || (processedCount == totalQuests && batchRecords.Count > 0))
            {
                try
                {
                    // Use InsertOrReplace to handle potential re-runs with existing data
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
                    reporter.Report((float)processedCount / totalQuests, $"Error inserting batch: {ex.Message}");
                    throw; // Re-throw to stop the export on error
                }

                // --- Progress Reporting ---
                float progress = (float)processedCount / totalQuests;
                reporter.Report(progress, $"Exported {recordCount} quests ({processedCount}/{totalQuests})...");
                await Task.Yield(); // Allow UI updates
            }
            else if (processedCount == totalQuests) // Ensure final report if last item didn't fill a batch
            {
                 reporter.Report(1.0f, $"Exported {recordCount} quests ({processedCount}/{totalQuests})...");
            }
        }
    }

    // Helper method to convert a Quest ScriptableObject to a QuestDBRecord
    private QuestDBRecord ExportQuest(Quest quest, int questDbIndex)
    {
        // Assuming BaseScriptableObject provides a unique string Id property
        if (quest == null || string.IsNullOrEmpty(quest.DBName)) return null;

        // Use Item.Id (assuming it exists via BaseScriptableObject)
        string requiredItems = quest.RequiredItems != null
            ? string.Join(", ", quest.RequiredItems.Where(item => item != null && !string.IsNullOrEmpty(item.Id)).Select(item => item.Id)) // Use Id and filter null/empty IDs
            : "";

        // Use WorldFaction.REFNAME
        string affectedFactions = quest.AffectFactions != null
            ? string.Join(", ", quest.AffectFactions.Where(f => f != null && !string.IsNullOrEmpty(f.REFNAME)).Select(f => f.REFNAME))
            : "";

        string affectedFactionAmounts = quest.AffectFactionAmts != null
            ? string.Join(", ", quest.AffectFactionAmts) // Convert floats to string implicitly
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
            ItemOnCompleteId = quest.ItemOnComplete?.Id, // Use ?. for safety
            GoldOnComplete = quest.GoldOnComplete,
            AssignNewQuestOnCompleteDBName = quest.AssignNewQuestOnComplete?.DBName, // Use ?. for safety
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
            ResourceName = quest.name // Store the asset name
        };
    }
}
