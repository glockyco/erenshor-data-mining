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

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(ClassDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        reportProgress(0, 0);

        // --- Data Fetching ---
        string[] guids = AssetDatabase.FindAssets("t:Class");
        int totalAssetsToLoad = guids.Length;

        if (totalAssetsToLoad == 0)
        {
            reportProgress(0, 0);
            Debug.LogWarning("No Class assets found. Skipping export step.");
            return;
        }

        List<Class> validClasses = new List<Class>();
        List<string> assetPaths = new List<string>();
        int assetsLoaded = 0;

        for (int i = 0; i < totalAssetsToLoad; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            string path = AssetDatabase.GUIDToAssetPath(guids[i]);
            Class classAsset = AssetDatabase.LoadAssetAtPath<Class>(path);
            if (classAsset != null && !string.IsNullOrEmpty(classAsset.ClassName))
            {
                validClasses.Add(classAsset);
                assetPaths.Add(path);
            }
            else
            {
                 Debug.LogWarning($"Skipped class asset at path '{path}' because it was null or had an empty ClassName.");
            }
            assetsLoaded++;
            if (i % 10 == 0 || i == totalAssetsToLoad - 1)
            {
                reportProgress(assetsLoaded, totalAssetsToLoad);
                await Task.Yield();
            }
        }


        int totalClasses = validClasses.Count;
        if (totalClasses == 0)
        {
            reportProgress(totalAssetsToLoad, totalAssetsToLoad);
            Debug.LogWarning("No valid class assets found (null or missing ClassName).");
            return;
        }

        reportProgress(0, totalClasses);
        await Task.Yield();

        // --- Processing & DB Interaction ---
        int batchSize = 10;
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
                ResourceName = Path.GetFileNameWithoutExtension(assetPath),
            };

            batchRecords.Add(record);
            processedCount++;

            // --- Batch Insertion ---
            if (batchRecords.Count >= batchSize || (processedCount == totalClasses && batchRecords.Count > 0))
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
                    Debug.LogError($"Error inserting class batch (around {classAsset.ClassName}): {ex.Message}");
                    reportProgress(processedCount, totalClasses);
                    throw;
                }

                // --- Progress Reporting ---
                reportProgress(processedCount, totalClasses);
                await Task.Yield();
            }
        }

        reportProgress(processedCount, totalClasses);
        Debug.Log($"Finished exporting {recordCount} classes from {processedCount} valid assets.");
    }
}
