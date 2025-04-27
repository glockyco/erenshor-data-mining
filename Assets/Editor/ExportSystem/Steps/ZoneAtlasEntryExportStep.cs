using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEngine; // Required for Resources.LoadAll, Debug

public class ZoneAtlasEntryExportStep : IExportStep
{
    // --- Metadata ---
    public string StepName => "Zone Atlas Entries";

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(ZoneAtlasEntryDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        reportProgress(0, 0);

        // --- Data Fetching ---
        ZoneAtlasEntry[] atlasEntries = Resources.LoadAll<ZoneAtlasEntry>("atlases");

        if (atlasEntries == null || atlasEntries.Length == 0)
        {
            reportProgress(0, 0);
            Debug.LogWarning("No ZoneAtlasEntry assets found in 'Resources/atlases'. Skipping export step.");
            return;
        }

        // Filter out entries without an Id, as it's the primary key.
        var validEntriesWithIndex = atlasEntries
            .Select((entry, index) => new { Entry = entry, Index = index })
            .Where(item => item.Entry != null && !string.IsNullOrEmpty(item.Entry.Id))
            .ToArray();

        int skippedCount = atlasEntries.Length - validEntriesWithIndex.Length;
        if (skippedCount > 0)
        {
            Debug.LogWarning($"Skipped {skippedCount} zone atlas entry(s) that were null or had missing Id.");
        }

        int totalEntries = validEntriesWithIndex.Length;

        if (totalEntries == 0)
        {
            reportProgress(0, 0);
            Debug.LogWarning("No valid zone atlas entries found (missing Id).");
            return;
        }

        reportProgress(0, totalEntries);
        await Task.Yield();

        // --- Processing & DB Interaction ---
        int batchSize = 30;
        var batchRecords = new List<ZoneAtlasEntryDBRecord>();
        int processedCount = 0;
        int recordCount = 0;

        foreach (var item in validEntriesWithIndex)
        {
            cancellationToken.ThrowIfCancellationRequested();

            ZoneAtlasEntry entry = item.Entry;
            int dbIndex = item.Index;

            // --- Extraction Logic ---
            string neighboringZones = string.Join(", ", entry.NeighboringZones ?? new List<string>());

            ZoneAtlasEntryDBRecord record = new ZoneAtlasEntryDBRecord
            {
                AtlasIndex = dbIndex,
                Id = entry.Id,
                ZoneName = entry.ZoneName,
                LevelRangeLow = entry.LevelRangeLow,
                LevelRangeHigh = entry.LevelRangeHigh,
                Dungeon = entry.Dungeon,
                NeighboringZones = neighboringZones,
                ResourceName = entry.name,
            };

            batchRecords.Add(record);
            processedCount++;

            // --- Batch Insertion ---
            if (batchRecords.Count >= batchSize || (processedCount == totalEntries && batchRecords.Count > 0))
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
                    Debug.LogError($"Error inserting zone atlas entry batch (around {entry.Id}): {ex.Message}");
                    reportProgress(processedCount, totalEntries);
                    throw;
                }

                // --- Progress Reporting ---
                reportProgress(processedCount, totalEntries);
                await Task.Yield();
            }
        }

        reportProgress(processedCount, totalEntries);
        Debug.Log($"Finished exporting {recordCount} zone atlas entries from {processedCount} valid assets.");
    }
}
