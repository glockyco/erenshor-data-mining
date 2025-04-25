using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEngine;

public class SpellExportStep : IExportStep
{
    public const string SPELLS_PATH = "Spells"; // Path within Resources folder

    // --- Metadata ---
    public string StepName => "Spells";
    public float ProgressWeight => 1.5f;

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(SpellDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, IProgressReporter reporter, CancellationToken cancellationToken)
    {
        reporter.Report(0f, "Loading spell assets...");

        // --- Data Fetching (Unity API - Resources.LoadAll) ---
        Spell[] spells = Resources.LoadAll<Spell>(SPELLS_PATH);
        // Filter out spells without an ID, as it's the primary key
        var validSpells = spells.Where(s => s != null && !string.IsNullOrEmpty(s.Id)).ToArray();
        int skippedCount = spells.Length - validSpells.Length;
        if (skippedCount > 0)
        {
            Debug.LogWarning($"Skipped {skippedCount} spell(s) that were null or had missing IDs.");
        }

        int totalSpells = validSpells.Length;

        if (totalSpells == 0)
        {
            reporter.Report(1f, "No valid spell assets found.");
            return;
        }

        reporter.Report(0.05f, $"Found {totalSpells} valid spells. Exporting...");
        await Task.Yield();

        // --- Processing & DB Interaction ---
        int batchSize = 50;
        var batchRecords = new List<SpellDBRecord>();
        int processedCount = 0;
        int recordCount = 0;

        for (int i = 0; i < totalSpells; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            Spell spell = validSpells[i];
            // ID/null check already done in filtering step

            // --- Extraction Logic (Using helper) ---
            SpellDBRecord record = ExportSpell(spell, i); // Pass index 'i'
            if (record != null) // Should generally not be null after filtering
            {
                batchRecords.Add(record);
            }

            processedCount++;

            // --- Batch Insertion ---
            if (batchRecords.Count >= batchSize || (processedCount == totalSpells && batchRecords.Count > 0))
            {
                try
                {
                    db.RunInTransaction(() =>
                    {
                        // Call InsertOrReplace for each record individually within the transaction
                        foreach (var record in batchRecords)
                        {
                            db.InsertOrReplace(record); // Use InsertOrReplace based on SpellDBRecord PK (Id)
                        }
                    });
                    recordCount += batchRecords.Count;
                    batchRecords.Clear();
                }
                catch (Exception ex)
                {
                    Debug.LogError($"Error inserting spell batch (around index {i}): {ex.Message}");
                    reporter.Report((float)processedCount / totalSpells, $"Error inserting batch: {ex.Message}");
                    throw;
                }

                // --- Progress Reporting ---
                float progress = (float)processedCount / totalSpells;
                reporter.Report(progress, $"Exported {recordCount} spells ({processedCount}/{totalSpells})...");
                await Task.Yield();
            }
            else if (processedCount == totalSpells)
            {
                reporter.Report(1.0f, $"Exported {recordCount} spells ({processedCount}/{totalSpells})...");
            }
        }
    }

    // Helper method to convert a Spell ScriptableObject to a SpellDBRecord (Adapted from SpellExporter)
    private SpellDBRecord ExportSpell(Spell spell, int spellDbIndex)
    {
        // Basic null/ID check already done, but included for safety if used elsewhere
        if (spell == null || string.IsNullOrEmpty(spell.Id)) return null;

        // Process the UsedBy list
        string classesString = "";
        if (spell.UsedBy != null && spell.UsedBy.Count > 0)
        {
            var classNames = spell.UsedBy
                .Where(c => c != null && !string.IsNullOrEmpty(c.ClassName)) // Ensure class and name are valid
                .Select(c => c.ClassName);
            classesString = string.Join(", ", classNames); // Use comma as separator
        }

        return new SpellDBRecord
        {
            // --- Core Identification ---
            SpellDBIndex = spellDbIndex,
            Id = spell.Id,
            SpellName = spell.SpellName,
            Type = spell.Type.ToString(),
            Line = spell.Line.ToString(),

            // --- Requirements & Cost ---
            Classes = classesString,
            RequiredLevel = spell.RequiredLevel,
            ManaCost = spell.ManaCost,

            // --- Simulation ---
            SimUsable = spell.SimUsable,

            // --- Aggro ---
            Aggro = spell.Aggro,

            // --- Timing ---
            SpellChargeTime = spell.SpellChargeTime,
            Cooldown = spell.Cooldown,
            SpellDurationInTicks = spell.SpellDurationInTicks,
            UnstableDuration = spell.UnstableDuration,
            InstantEffect = spell.InstantEffect,

            // --- Targeting & Type ---
            SpellRange = spell.SpellRange,
            SelfOnly = spell.SelfOnly,
            MaxLevelTarget = spell.MaxLevelTarget,
            GroupEffect = spell.GroupEffect,
            CanHitPlayers = spell.CanHitPlayers,
            ApplyToCaster = spell.ApplyToCaster,

            // --- Core Effects (Damage/Heal/Shield) ---
            TargetDamage = spell.TargetDamage,
            TargetHealing = spell.TargetHealing,
            CasterHealing = spell.CasterHealing,
            ShieldingAmt = spell.ShieldingAmt,
            Lifetap = spell.Lifetap,
            DamageType = spell.MyDamageType.ToString(),
            ResistModifier = spell.ResistModifier,

            // --- Stat Buffs/Debuffs ---
            HP = spell.HP,
            AC = spell.AC,
            Mana = spell.Mana,
            MovementSpeed = spell.MovementSpeed,
            Str = spell.Str,
            Dex = spell.Dex,
            End = spell.End,
            Agi = spell.Agi,
            Wis = spell.Wis,
            Int = spell.Int,
            Cha = spell.Cha,
            MR = spell.MR,
            ER = spell.ER,
            PR = spell.PR,
            VR = spell.VR,
            DamageShield = spell.DamageShield,
            Haste = spell.Haste,
            PercentLifesteal = spell.percentLifesteal,
            AtkRollModifier = spell.AtkRollModifier,

            // --- Control Effects ---
            RootTarget = spell.RootTarget,
            StunTarget = spell.StunTarget,
            CharmTarget = spell.CharmTarget,
            CrowdControlSpell = spell.CrowdControlSpell,
            BreakOnDamage = spell.BreakOnDamage,
            TauntSpell = spell.TauntSpell,

            // --- Special Mechanics ---
            PetToSummonResourceName = spell.PetToSummon != null ? spell.PetToSummon.name : null,
            StatusEffectToApplyId = spell.StatusEffectToApply != null ? spell.StatusEffectToApply.Id : null,
            ReapAndRenew = spell.ReapAndRenew,
            ResonateChance = spell.ResonateChance,
            XPBonus = spell.XPBonus,
            AutomateAttack = spell.AutomateAttack,

            // --- Visual/Audio ---
            SpellChargeFXIndex = spell.SpellChargeFXIndex,
            SpellResolveFXIndex = spell.SpellResolveFXIndex,
            SpellIconName = spell.SpellIcon != null ? spell.SpellIcon.name : null,
            ShakeDur = spell.ShakeDur,
            ShakeAmp = spell.ShakeAmp,
            ColorR = spell.color.r,
            ColorG = spell.color.g,
            ColorB = spell.color.b,
            ColorA = spell.color.a,

            // --- Text/Metadata ---
            StatusEffectMessageOnPlayer = spell.StatusEffectMessageOnPlayer,
            StatusEffectMessageOnNPC = spell.StatusEffectMessageOnNPC,
            SpellDesc = spell.SpellDesc,

            // --- Internals ---
            ResourceName = spell.name, // Store the ScriptableObject's name
        };
    }
}