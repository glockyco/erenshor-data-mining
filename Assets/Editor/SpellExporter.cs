using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SQLite;
using UnityEngine;

public class SpellExporter
{
    public const string SPELLS_PATH = "Spells"; // Path within Resources folder
    private readonly DatabaseManager _dbManager;

    public SpellExporter()
    {
        _dbManager = new DatabaseManager();
    }

    // Asynchronous export for spells only
    public void ExportSpellsToDBAsync(DatabaseOperation.ProgressCallback progressCallback = null)
    {
        var state = new Dictionary<string, object>
        {
            { "stage", "init" },
            { "dbPath", Path.Combine(Application.dataPath, DatabaseOperation.DB_PATH) },
            { "db", null },
            { "spells", null },
            { "spellIndex", 0 },
            { "spellCount", 0 },
            { "totalSpells", 0 },
            { "completed", false },
            { "progressCallback", progressCallback }
        };

        var stageOperations = new Dictionary<string, DatabaseManager.ExportOperation>
        {
            { "init", InitializeSpellsDB },
            { "prepare_spells", PrepareSpells },
            { "export_spells", ExportSpellsBatch }
        };

        _dbManager.ExportAsync(state,
            (s, callback) => _dbManager.GenericExportAsyncUpdate(s, callback, stageOperations, "Exported {0[spellCount]} spells"),
            progressCallback);
    }

    // Initialize the database for spells export
    private void InitializeSpellsDB(SQLiteConnection db, Dictionary<string, object> state)
    {
        db.CreateTable<SpellDBRecord>();
        db.DeleteAll<SpellDBRecord>();

        state["stage"] = "prepare_spells";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.1f, "Spell database initialized");
    }

    // Prepare spell data for export
    public void PrepareSpells(SQLiteConnection db, Dictionary<string, object> state)
    {
        Spell[] spells = Resources.LoadAll<Spell>(SPELLS_PATH);
        // Filter out spells without an ID, as it's the primary key
        var validSpells = spells.Where(s => s != null && !string.IsNullOrEmpty(s.Id)).ToArray();
        int skippedCount = spells.Length - validSpells.Length;
        if (skippedCount > 0)
        {
            Debug.LogWarning($"Skipped {skippedCount} spell(s) that were null or had missing IDs.");
        }

        state["spells"] = validSpells;
        state["totalSpells"] = validSpells.Length;

        state["stage"] = "export_spells";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.2f, $"Found {validSpells.Length} valid spells");
    }

    // Export a batch of spells
    public void ExportSpellsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        Spell[] allSpells = (Spell[])state["spells"];
        int spellIndex = (int)state["spellIndex"];
        int spellCount = (int)state["spellCount"];
        int totalSpells = (int)state["totalSpells"];

        int batchSize = 50; // Adjust batch size as needed
        int endIndex = Math.Min(spellIndex + batchSize, totalSpells);

        db.BeginTransaction();
        try
        {
            var records = new List<SpellDBRecord>();
            for (int i = spellIndex; i < endIndex; i++)
            {
                Spell spell = allSpells[i];
                // ID/null check already done in PrepareSpells
                SpellDBRecord record = ExportSpell(spell);
                if (record != null) // ExportSpell might return null if essential data is missing
                {
                    records.Add(record);
                }
            }

            // Use InsertOrReplace in case of duplicates (though ID should be unique)
            foreach (var record in records)
            {
                db.InsertOrReplace(record);
            }
            spellCount += records.Count;

            db.Commit();
        }
        catch (Exception ex)
        {
            db.Rollback();
            Debug.LogError($"Error exporting spells batch ({spellIndex}-{endIndex - 1}): {ex.Message}\n{ex.StackTrace}");
        }

        state["spellIndex"] = endIndex;
        state["spellCount"] = spellCount;

        float progress = 0.2f + (0.8f * (totalSpells > 0 ? (float)endIndex / totalSpells : 1.0f));
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Exported {spellCount}/{totalSpells} spells");

        if (endIndex >= totalSpells)
        {
            state["completed"] = true;
        }
    }

    // Helper method to convert a Spell ScriptableObject to a SpellDBRecord
    public SpellDBRecord ExportSpell(Spell spell)
    {
        // Basic null check already done, but double-check ID
        if (spell == null || string.IsNullOrEmpty(spell.Id))
        {
            // Warning already logged in PrepareSpells if ID was missing
            return null;
        }

        // Process the UsedBy list
        string classesString = "";
        if (spell.UsedBy != null && spell.UsedBy.Count > 0)
        {
            var classNames = spell.UsedBy
                .Where(c => c != null && !string.IsNullOrEmpty(c.ClassName)) // Ensure class and name are valid
                .Select(c => c.ClassName);
            classesString = string.Join(",", classNames); // Use comma as separator
        }

        return new SpellDBRecord
        {
            // --- Core Identification ---
            Id = spell.Id,
            SpellName = spell.SpellName,

            // --- Requirements & Cost ---
            RequiredLevel = spell.RequiredLevel,
            ManaCost = spell.ManaCost,
            Classes = classesString,

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
            Type = spell.Type.ToString(),
            Line = spell.Line.ToString(),
            SpellRange = spell.SpellRange,
            SelfOnly = spell.SelfOnly,
            MaxLevelTarget = spell.MaxLevelTarget,
            GroupEffect = spell.GroupEffect,
            CanHitPlayers = spell.CanHitPlayers,

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
            ApplyToCaster = spell.ApplyToCaster,
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
            ResourceName = spell.name,
        };
    }
}
