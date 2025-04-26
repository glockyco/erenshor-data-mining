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
    public float ProgressWeight => 0.6f; // Adjust weight as needed

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(ZoneAtlasEntryDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, IProgressReporter reporter, CancellationToken cancellationToken)
    {
        reporter.Report(0f, "Loading zone atlas assets...");

        // --- Data Fetching ---
        ZoneAtlasEntry[] atlasEntries = Resources.LoadAll<ZoneAtlasEntry>("atlases");

        if (atlasEntries == null || atlasEntries.Length == 0)
        {
            reporter.Report(1f, "No zone atlas assets found in Resources/atlases.");
            Debug.LogWarning("No ZoneAtlasEntry assets found in 'Resources/atlases'. Skipping export step.");
            return;
        }

        // Filter out entries without an Id, as it's the primary key, but keep track of original index
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
            reporter.Report(1f, "No valid zone atlas entries found (missing Id).");
            return;
        }

        reporter.Report(0.05f, $"Found {totalEntries} valid zone atlas entries. Exporting...");
        await Task.Yield(); // Allow UI update

        // --- Processing & DB Interaction ---
        int batchSize = 30; // Adjust batch size as needed
        var batchRecords = new List<ZoneAtlasEntryDBRecord>();
        int processedCount = 0;
        int recordCount = 0;

        foreach (var item in validEntriesWithIndex)
        {
            cancellationToken.ThrowIfCancellationRequested();

            ZoneAtlasEntry entry = item.Entry;
            int dbIndex = item.Index; // Get the original index

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
                    // Use InsertOrReplace based on Id primary key
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
                    reporter.Report((float)processedCount / totalEntries, $"Error inserting batch: {ex.Message}");
                    throw; // Stop export on error
                }

                // --- Progress Reporting ---
                float progress = (float)processedCount / totalEntries;
                reporter.Report(progress, $"Exported {recordCount} zone atlas entries ({processedCount}/{totalEntries})...");
                await Task.Yield(); // Allow UI updates
            }
        }

        // Ensure final report
        reporter.Report(1.0f, $"Exported {recordCount} zone atlas entries ({processedCount}/{totalEntries}).");
    }
}
