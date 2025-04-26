using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEngine; // Required for Debug

public class FactionExportStep : IExportStep
{
    // --- Metadata ---
    public string StepName => "Factions";
    public float ProgressWeight => 0.5f; // Adjust weight relative to other steps

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(FactionDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, IProgressReporter reporter, CancellationToken cancellationToken)
    {
        reporter.Report(0f, "Loading faction assets...");

        // --- Data Fetching (Using GlobalFactionManager) ---
        GlobalFactionManager.LoadFactions();
        WorldFaction[] factions = GlobalFactionManager.FactionDB;

        // Filter out factions without a REFNAME, as it's the primary key
        var validFactions = factions
            .Select((faction, index) => new { Faction = faction, Index = index }) // Keep track of original index
            .Where(item => item.Faction != null && !string.IsNullOrEmpty(item.Faction.REFNAME))
            .ToArray();

        int skippedCount = factions.Length - validFactions.Length;
        if (skippedCount > 0)
        {
            Debug.LogWarning($"Skipped {skippedCount} faction(s) that were null or had missing REFNAME.");
        }

        int totalFactions = validFactions.Length;

        if (totalFactions == 0)
        {
            reporter.Report(1f, "No valid faction assets found.");
            return;
        }

        reporter.Report(0.05f, $"Found {totalFactions} valid factions. Exporting...");
        await Task.Yield(); // Allow UI update

        // --- Processing & DB Interaction ---
        int batchSize = 20; // Factions are likely few, smaller batch is fine
        var batchRecords = new List<FactionDBRecord>();
        int processedCount = 0;
        int recordCount = 0;

        foreach (var item in validFactions)
        {
            cancellationToken.ThrowIfCancellationRequested();

            WorldFaction faction = item.Faction;
            int factionDbIndex = item.Index; // Use the original index

            // --- Extraction Logic ---
            FactionDBRecord record = new FactionDBRecord
            {
                REFNAME = faction.REFNAME,
                FactionDBIndex = factionDbIndex,
                FactionName = faction.FactionName,
                FactionDesc = faction.FactionDesc,
                DefaultValue = faction.DEFAULTVAL,
                ResourceName = faction.name,
            };

            batchRecords.Add(record);
            processedCount++;

            // --- Batch Insertion ---
            if (batchRecords.Count >= batchSize || (processedCount == totalFactions && batchRecords.Count > 0))
            {
                try
                {
                    // Use InsertOrReplace based on REFNAME primary key
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
                    Debug.LogError($"Error inserting faction batch (around index {item.Index}): {ex.Message}");
                    reporter.Report((float)processedCount / totalFactions, $"Error inserting batch: {ex.Message}");
                    throw; // Stop export on error
                }

                // --- Progress Reporting ---
                float progress = (float)processedCount / totalFactions;
                reporter.Report(progress, $"Exported {recordCount} factions ({processedCount}/{totalFactions})...");
                await Task.Yield(); // Allow UI updates
            }
        }
         // Ensure final report if the loop finished without a full batch report
        if (processedCount == totalFactions)
        {
             reporter.Report(1.0f, $"Exported {recordCount} factions ({processedCount}/{totalFactions}).");
        }
    }
}
