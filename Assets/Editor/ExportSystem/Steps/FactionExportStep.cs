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
    // ProgressWeight removed

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(WorldFactionDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        reportProgress(0, 0);

        // --- Data Fetching ---
        GlobalFactionManager.LoadFactions();
        WorldFaction[] factions = GlobalFactionManager.FactionDB;

        // Filter out factions without a REFNAME, as it's the primary key.
        var validFactions = factions
            .Select((faction, index) => new { Faction = faction, Index = index })
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
            reportProgress(0, 0);
            Debug.LogWarning("No valid faction assets found.");
            return;
        }

        reportProgress(0, totalFactions);
        await Task.Yield();

        // --- Processing & DB Interaction ---
        int batchSize = 20;
        var batchRecords = new List<WorldFactionDBRecord>();
        int processedCount = 0;
        int recordCount = 0;

        foreach (var item in validFactions)
        {
            cancellationToken.ThrowIfCancellationRequested();

            WorldFaction faction = item.Faction;
            int factionDbIndex = item.Index;

            // --- Extraction Logic ---
            WorldFactionDBRecord record = new WorldFactionDBRecord
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
                    reportProgress(processedCount, totalFactions);
                    throw;
                }

                // --- Progress Reporting ---
                reportProgress(processedCount, totalFactions);
                await Task.Yield();
            }
        }
        
        reportProgress(processedCount, totalFactions);
        Debug.Log($"Finished exporting {recordCount} factions from {processedCount} valid assets.");
    }
}
