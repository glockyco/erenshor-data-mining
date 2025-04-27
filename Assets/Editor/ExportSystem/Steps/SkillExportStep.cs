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

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(SkillDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        reportProgress(0, 0);

        // --- Data Fetching ---
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
            reportProgress(0, 0);
            Debug.LogWarning("No valid skill assets found.");
            return;
        }

        reportProgress(0, totalSkills);
        await Task.Yield();

        // --- Processing & DB Interaction ---
        int batchSize = 50;
        var batchRecords = new List<SkillDBRecord>();
        int processedCount = 0;
        int recordCount = 0;

        for (int i = 0; i < totalSkills; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            Skill skill = validSkills[i];

            // --- Extraction Logic) ---
            SkillDBRecord record = ExportSkill(skill, i);
            if (record != null)
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
                    Debug.LogError($"Error inserting skill batch (around index {i}): {ex.Message}");
                    reportProgress(processedCount, totalSkills);
                    throw;
                }

                // --- Progress Reporting ---
                reportProgress(processedCount, totalSkills);
                await Task.Yield();
            }
        }
        
        reportProgress(processedCount, totalSkills);
        Debug.Log($"Finished exporting {recordCount} skills from {processedCount} valid assets.");
    }

    private SkillDBRecord ExportSkill(Skill skill, int skillDbIndex)
    {
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
