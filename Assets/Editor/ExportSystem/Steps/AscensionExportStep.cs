using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEngine;

public class AscensionExportStep : IExportStep
{
    // --- Metadata ---
    public string StepName => "Ascensions";

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(AscensionDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        reportProgress(0, 0);

        // --- Data Fetching ---
        Ascension[] ascensions = Resources.LoadAll<Ascension>("Ascensions");

        if (ascensions == null || ascensions.Length == 0)
        {
            reportProgress(0, 0);
            Debug.LogWarning("No Ascension assets found in 'Resources/Ascensions'. Skipping export step.");
            return;
        }

        // Filter out ascensions without an Id, as it's the primary key.
        var validAscensionsWithIndex = ascensions
            .Select((ascension, index) => new { Ascension = ascension, Index = index })
            .Where(item => item.Ascension != null && !string.IsNullOrEmpty(item.Ascension.Id))
            .ToArray();

        int skippedCount = ascensions.Length - validAscensionsWithIndex.Length;
        if (skippedCount > 0)
        {
            Debug.LogWarning($"Skipped {skippedCount} ascension(s) that were null or had missing Id.");
        }

        int totalAscensions = validAscensionsWithIndex.Length;

        if (totalAscensions == 0)
        {
            reportProgress(0, 0);
            Debug.LogWarning("No valid ascension assets found (missing Id).");
            return;
        }

        reportProgress(0, totalAscensions);
        await Task.Yield();

        // --- Processing & DB Interaction ---
        int batchSize = 50;
        var batchRecords = new List<AscensionDBRecord>();
        int processedCount = 0;
        int recordCount = 0;

        foreach (var item in validAscensionsWithIndex)
        {
            cancellationToken.ThrowIfCancellationRequested();

            Ascension ascension = item.Ascension;
            int dbIndex = item.Index;

            // --- Extraction Logic ---
            AscensionDBRecord record = new AscensionDBRecord
            {
                AscensionDBIndex = dbIndex,
                Id = ascension.Id,

                UsedBy = ascension.UsedBy.ToString(),
                SkillName = ascension.SkillName,
                SkillDesc = ascension.SkillDesc,
                MaxRank = ascension.MaxRank,
                SimPlayerWeight = ascension.SimPlayerWeight,

                // General
                IncreaseHP = ascension.IncreaseHP,
                IncreaseDEF = ascension.IncreaseDEF,
                IncreaseMana = ascension.IncreaseMana,
                MR = ascension.MR,
                PR = ascension.PR,
                ER = ascension.ER,
                VR = ascension.VR,
                IncreaseDodge = ascension.IncreaseDodge,

                // Duelist
                IncreaseCombatRoll = ascension.IncreaseCombatRoll,
                DecreaseAggroGen = ascension.DecreaseAggroGen,
                ChanceForExtraAttack = ascension.ChanceForExtraAttack,
                ChanceForDoubleBackstab = ascension.ChanceForDoubleBackstab,
                ChanceToCritBackstab = ascension.ChanceToCritBackstab,

                // Arcanist
                ResistModIncrease = ascension.ResistModIncrease,
                DecreaseSpellAggroGen = ascension.DecreaseSpellAggroGen,
                TripleResonateChance = ascension.TripleResonateChance,
                CooldownReduction = ascension.CooldownReduction,
                IntelligenceScaling = ascension.IntelligenceScaling,

                // Paladin
                TripleAttackChance = ascension.TripleAttackChance,
                AggroGenIncrease = ascension.AggroGenIncrease,
                MitigationIncrease = ascension.MitigationIncrease,
                AdvancedIncreaseHP = ascension.AdvancedIncreaseHP,
                AdvancedResists = ascension.AdvancedResists,

                // Druid
                HealingIncrease = ascension.HealingIncrease,
                CriticalDotChance = ascension.CriticalDotChance,
                CriticalHealingChance = ascension.CriticalHealingChance,
                VengefulHealingPercentage = ascension.VengefulHealingPercentage,
                SummonedBeastEnhancement = ascension.SummonedBeastEnhancement,

                ResourceName = ascension.name
            };

            batchRecords.Add(record);
            processedCount++;

            // --- Batch Insertion ---
            if (batchRecords.Count >= batchSize || (processedCount == totalAscensions && batchRecords.Count > 0))
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
                    Debug.LogError($"Error inserting ascension batch (around {ascension.Id}): {ex.Message}");
                    reportProgress(processedCount, totalAscensions);
                    throw;
                }

                // --- Progress Reporting ---
                reportProgress(processedCount, totalAscensions);
                await Task.Yield();
            }
        }

        reportProgress(processedCount, totalAscensions);
        Debug.Log($"Finished exporting {recordCount} ascensions from {processedCount} valid assets.");
    }
}
