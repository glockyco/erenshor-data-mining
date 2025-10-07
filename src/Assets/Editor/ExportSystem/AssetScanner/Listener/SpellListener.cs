#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;

public class SpellListener : IAssetScanListener<Spell>
{
    private readonly SQLiteConnection _db;
    private readonly List<SpellRecord> _records = new();
    private readonly List<SpellClassRecord> _spellClassRecords = new();

    public SpellListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<SpellRecord>();
        _db.CreateTable<SpellClassRecord>();

        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<SpellRecord>();
            _db.DeleteAll<SpellClassRecord>();

            _db.InsertAll(_records);
            _db.InsertAll(_spellClassRecords);
        });
        _records.Clear();
        _spellClassRecords.Clear();
    }

    public void OnAssetFound(Spell asset)
    {
        var record = CreateRecord(asset, _records.Count);
        if (record != null)
        {
            _records.Add(record);
            _spellClassRecords.AddRange(CreateSpellClassRecords(asset, _records.Count - 1));
        }
    }

    private SpellRecord CreateRecord(Spell spell, int spellDbIndex)
    {
        if (spell == null) return null;

        string classesString = "";
        if (spell.UsedBy is { Count: > 0 })
        {
            var classNames = spell.UsedBy
                .Where(c => c != null && !string.IsNullOrEmpty(c.ClassName))
                .Select(c => c.ClassName);
            classesString = string.Join(", ", classNames);
        }
        
        string? spellIconName = null;
        if (spell.SpellIcon != null)
        {
            var path = AssetDatabase.GetAssetPath(spell.SpellIcon);
            spellIconName = System.IO.Path.GetFileNameWithoutExtension(path);
        }

        return new SpellRecord
        {
            // --- Core Identification ---
            SpellDBIndex = spellDbIndex,
            Id = spell.Id,
            SpellName = spell.SpellName,
            SpellDesc = spell.SpellDesc,
            SpecialDescriptor = spell.SpecialDescriptor,
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
            AddProc = spell.AddProc is not null ? $"{spell.AddProc.SpellName} ({spell.AddProc.Id})" : "",
            AddProcChance = spell.AddProcChance,

            // --- Stat Buffs/Debuffs ---
            HP = spell.HP,
            AC = spell.AC,
            Mana = spell.Mana,
            PercentManaRestoration = spell.PercentManaRestoration,
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
            BleedDamagePercent = spell.BleedDamagePercent,

            // --- Control Effects ---
            RootTarget = spell.RootTarget,
            StunTarget = spell.StunTarget,
            CharmTarget = spell.CharmTarget,
            CrowdControlSpell = spell.CrowdControlSpell,
            BreakOnDamage = spell.BreakOnDamage,
            BreakOnAnyAction = spell.BreakOnAnyAction,
            TauntSpell = spell.TauntSpell,

            // --- Special Mechanics ---
            PetToSummonResourceName = spell.PetToSummon != null ? spell.PetToSummon.name : null,
            StatusEffectToApply = spell.StatusEffectToApply is not null ? $"{spell.StatusEffectToApply.SpellName} ({spell.StatusEffectToApply.Id})" : "",
            ReapAndRenew = spell.ReapAndRenew,
            ResonateChance = spell.ResonateChance,
            XPBonus = spell.XPBonus,
            AutomateAttack = spell.AutomateAttack,
            WornEffect = spell.WornEffect,

            // --- Visual/Audio ---
            SpellChargeFXIndex = spell.SpellChargeFXIndex,
            SpellResolveFXIndex = spell.SpellResolveFXIndex,
            SpellIconName = spellIconName,
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

    private List<SpellClassRecord> CreateSpellClassRecords(Spell spell, int spellDbIndex)
    {
        var records = new List<SpellClassRecord>();

        if (spell.UsedBy is { Count: > 0 })
        {
            foreach (var characterClass in spell.UsedBy)
            {
                if (characterClass != null && !string.IsNullOrEmpty(characterClass.ClassName))
                {
                    records.Add(new SpellClassRecord
                    {
                        SpellId = spellDbIndex,
                        ClassName = characterClass.ClassName
                    });
                }
            }
        }

        return records;
    }
}