using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEditor;
using UnityEngine;

public class ClassExportStep : IExportStep
{
    // --- Metadata ---
    public string StepName => "Classes";
    public float ProgressWeight => 0.4f;

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(ClassDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, IProgressReporter reporter, CancellationToken cancellationToken)
    {
        reporter.Report(0f, "Finding class assets...");

        // --- Data Fetching ---
        string[] guids = AssetDatabase.FindAssets("t:Class");

        if (guids == null || guids.Length == 0)
        {
            reporter.Report(1f, "No class assets found.");
            Debug.LogWarning("No Class assets found. Skipping export step.");
            return;
        }

        List<Class> validClasses = new List<Class>();
        List<string> assetPaths = new List<string>();

        // Load assets based on GUIDs
        for (int i = 0; i < guids.Length; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            string path = AssetDatabase.GUIDToAssetPath(guids[i]);
            Class classAsset = AssetDatabase.LoadAssetAtPath<Class>(path);
            if (classAsset != null && !string.IsNullOrEmpty(classAsset.ClassName)) // Check for null and valid ClassName (PK)
            {
                validClasses.Add(classAsset);
                assetPaths.Add(path);
            }
            else
            {
                 Debug.LogWarning($"Skipped class asset at path '{path}' because it was null or had an empty ClassName.");
            }
             // Report progress during asset loading phase
            if (i % 10 == 0) // Report every 10 assets processed
            {
                reporter.Report((float)i / guids.Length * 0.1f, $"Loading class assets ({i}/{guids.Length})...");
                await Task.Yield();
            }
        }


        int totalClasses = validClasses.Count;
        if (totalClasses == 0)
        {
            reporter.Report(1f, "No valid class assets found (null or missing ClassName).");
            return;
        }

        reporter.Report(0.1f, $"Found {totalClasses} valid classes. Exporting...");
        await Task.Yield(); // Allow UI update

        // --- Processing & DB Interaction ---
        int batchSize = 10; // Classes are few, very small batch is fine
        var batchRecords = new List<ClassDBRecord>();
        int processedCount = 0;
        int recordCount = 0;

        for(int i = 0; i < totalClasses; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            Class classAsset = validClasses[i];
            string assetPath = assetPaths[i];

            // --- Extraction Logic ---
            ClassDBRecord record = new ClassDBRecord
            {
                ClassName = classAsset.ClassName,
                MitigationBonus = classAsset.MitigationBonus,
                StrBenefit = classAsset.StrBenefit,
                EndBenefit = classAsset.EndBenefit,
                DexBenefit = classAsset.DexBenefit,
                AgiBenefit = classAsset.AgiBenefit,
                IntBenefit = classAsset.IntBenefit,
                WisBenefit = classAsset.WisBenefit,
                ChaBenefit = classAsset.ChaBenefit,
                AggroMod = classAsset.AggroMod,
                ResourceName = Path.GetFileNameWithoutExtension(assetPath), // Get filename from path
            };

            batchRecords.Add(record);
            processedCount++;

            // --- Batch Insertion ---
            if (batchRecords.Count >= batchSize || (processedCount == totalClasses && batchRecords.Count > 0))
            {
                try
                {
                    // Use InsertOrReplace based on ClassName primary key
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
                    Debug.LogError($"Error inserting class batch (around {classAsset.ClassName}): {ex.Message}");
                    reporter.Report(0.1f + (float)processedCount / totalClasses * 0.9f, $"Error inserting batch: {ex.Message}");
                    throw; // Stop export on error
                }

                // --- Progress Reporting ---
                float progress = 0.1f + (float)processedCount / totalClasses * 0.9f; // Scale progress from 10% to 100%
                reporter.Report(progress, $"Exported {recordCount} classes ({processedCount}/{totalClasses})...");
                await Task.Yield(); // Allow UI updates
            }
        }

        // Ensure final report
        reporter.Report(1.0f, $"Exported {recordCount} classes ({processedCount}/{totalClasses}).");
    }
}
