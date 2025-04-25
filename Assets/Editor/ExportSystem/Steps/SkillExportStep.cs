using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEngine;

public class SkillExportStep : IExportStep
{
    public const string SKILLS_PATH = "Skills"; // Path within Resources folder (from SkillDB.cs)

    // --- Metadata ---
    public string StepName => "Skills";
    public float ProgressWeight => 1.0f; // Adjust weight as needed

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(SkillDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, IProgressReporter reporter, CancellationToken cancellationToken)
    {
        reporter.Report(0f, "Loading skill assets...");

        // --- Data Fetching (Unity API - Resources.LoadAll) ---
        // Use the path identified in SkillDB.cs
        Skill[] skills = Resources.LoadAll<Skill>(SKILLS_PATH);
        // Filter out skills without an ID, as it's the primary key
        var validSkills = skills.Where(s => s != null && !string.IsNullOrEmpty(s.Id)).ToArray();
        int skippedCount = skills.Length - validSkills.Length;
        if (skippedCount > 0)
        {
            Debug.LogWarning($"Skipped {skippedCount} skill(s) that were null or had missing IDs.");
        }

        int totalSkills = validSkills.Length;

        if (totalSkills == 0)
        {
            reporter.Report(1f, "No valid skill assets found.");
            return;
        }

        reporter.Report(0.05f, $"Found {totalSkills} valid skills. Exporting...");
        await Task.Yield();

        // --- Processing & DB Interaction ---
        int batchSize = 50; // Same batch size as spells, adjust if needed
        var batchRecords = new List<SkillDBRecord>();
        int processedCount = 0;
        int recordCount = 0;

        for (int i = 0; i < totalSkills; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            Skill skill = validSkills[i];
            // ID/null check already done in filtering step

            // --- Extraction Logic (Using helper) ---
            SkillDBRecord record = ExportSkill(skill, i);
            if (record != null) // Should generally not be null after filtering
            {
                batchRecords.Add(record);
            }

            processedCount++;

            // --- Batch Insertion ---
            if (batchRecords.Count >= batchSize || (processedCount == totalSkills && batchRecords.Count > 0))
            {
                try
                {
                    db.RunInTransaction(() =>
                    {
                        // Call InsertOrReplace for each record individually within the transaction
                        foreach (var rec in batchRecords) // Renamed variable to avoid conflict
                        {
                            db.InsertOrReplace(rec); // Use InsertOrReplace based on SkillDBRecord PK (Id)
                        }
                    });
                    recordCount += batchRecords.Count;
                    batchRecords.Clear();
                }
                catch (Exception ex)
                {
                    Debug.LogError($"Error inserting skill batch (around index {i}): {ex.Message}");
                    reporter.Report((float)processedCount / totalSkills, $"Error inserting batch: {ex.Message}");
                    throw; // Re-throw to halt the export on error
                }

                // --- Progress Reporting ---
                float progress = (float)processedCount / totalSkills;
                reporter.Report(progress, $"Exported {recordCount} skills ({processedCount}/{totalSkills})...");
                await Task.Yield(); // Allow UI updates and cancellation checks
            }
            else if (processedCount == totalSkills) // Catch the case where the last batch is smaller than batchSize
            {
                 reporter.Report(1.0f, $"Exported {recordCount} skills ({processedCount}/{totalSkills})...");
            }
        }
         // Final report if loop finishes without hitting the batch condition exactly on the last item
        if (processedCount == totalSkills && recordCount < totalSkills) // Should ideally not happen with current logic, but safe check
        {
             reporter.Report(1.0f, $"Finished exporting {recordCount} skills.");
        }
    }

    // Helper method to convert a Skill ScriptableObject to a SkillDBRecord
    private SkillDBRecord ExportSkill(Skill skill, int skillDbIndex)
    {
        // Basic null/ID check already done, but included for safety if used elsewhere
        if (skill == null || string.IsNullOrEmpty(skill.Id)) return null;

        return new SkillDBRecord
        {
            // --- Core Identification ---
            SkillDBIndex = skillDbIndex,
            Id = skill.Id,
            SkillName = skill.SkillName,
            SkillDesc = skill.SkillDesc,
            TypeOfSkill = skill.TypeOfSkill.ToString(),

            // --- Requirements ---
            DuelistRequiredLevel = skill.DuelistRequiredLevel,
            PaladinRequiredLevel = skill.PaladinRequiredLevel,
            ArcanistRequiredLevel = skill.ArcanistRequiredLevel,
            DruidRequiredLevel = skill.DruidRequiredLevel,
            RequireBehind = skill.RequireBehind,
            Require2H = skill.Require2H,
            RequireDW = skill.RequireDW,
            RequireShield = skill.RequireShield,

            // --- Simulation ---
            SimPlayersAutolearn = skill.SimPlayersAutolearn,
            
            // --- Timing & Cost ---
            Cooldown = skill.Cooldown,

            // --- Effects & Mechanics ---
            Interrupt = skill.Interrupt,
            SpawnOnUseResourceName = skill.SpawnOnUse != null ? skill.SpawnOnUse.name : null,
            EffectToApplyId = skill.EffectToApply != null ? skill.EffectToApply.Id : null,
            AffectPlayer = skill.AffectPlayer,
            AffectTarget = skill.AffectTarget,
            SkillRange = skill.SkillRange,
            SkillPower = skill.SkillPower,
            PercentDmg = skill.PercentDmg,
            DamageType = skill.DmgType.ToString(),
            ScaleOffWeapon = skill.ScaleOffWeapon,
            ProcShield = skill.ProcShield,
            GuaranteeProc = skill.GuaranteeProc,
            AutomateAttack = skill.AutomateAttack,

            // --- Visual/Audio ---
            SkillAnimName = skill.SkillAnimName,
            SkillIconName = skill.SkillIcon != null ? skill.SkillIcon.name : null,

            // --- Text ---
            PlayerUses = skill.PlayerUses,
            NPCUses = skill.NPCUses,

            // --- Internals ---
            ResourceName = skill.name,
        };
    }
}
