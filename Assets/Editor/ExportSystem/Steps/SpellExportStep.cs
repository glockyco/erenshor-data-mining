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
    // ProgressWeight removed

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(SpellDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        reportProgress(0, 0);

        // --- Data Fetching ---
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
            reportProgress(0, 0);
            Debug.LogWarning("No valid spell assets found.");
            return;
        }

        reportProgress(0, totalSpells);
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

            // --- Extraction Logic ---
            SpellDBRecord record = ExportSpell(spell, i);
            if (record != null)
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
                    Debug.LogError($"Error inserting spell batch (around index {i}): {ex.Message}");
                    reportProgress(processedCount, totalSpells);
                    throw;
                }

                // --- Progress Reporting ---
                reportProgress(processedCount, totalSpells);
                await Task.Yield();
            }
        }
        
        reportProgress(processedCount, totalSpells);
        Debug.Log($"Finished exporting {recordCount} spells from {processedCount} valid assets.");
    }

    private SpellDBRecord ExportSpell(Spell spell, int spellDbIndex)
    {
        if (spell == null || string.IsNullOrEmpty(spell.Id)) return null;

        string classesString = "";
        if (spell.UsedBy != null && spell.UsedBy.Count > 0)
        {
            var classNames = spell.UsedBy
                .Where(c => c != null && !string.IsNullOrEmpty(c.ClassName))
                .Select(c => c.ClassName);
            classesString = string.Join(", ", classNames);
        }

        return new SpellDBRecord
        {
            // --- Core Identification ---
            SpellDBIndex = spellDbIndex,
            Id = spell.Id,
            SpellName = spell.SpellName,
            SpellDesc = spell.SpellDesc,
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

            // --- Internals ---
            ResourceName = spell.name,
        };
    }
}
