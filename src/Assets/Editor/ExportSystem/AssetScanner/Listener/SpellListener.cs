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
            _spellClassRecords.AddRange(CreateSpellClassRecords(asset));
        }
    }

    private SpellRecord CreateRecord(Spell spell, int spellDbIndex)
    {
        if (spell == null)
        {
            throw new System.ArgumentNullException(nameof(spell), "[SpellListener] Cannot create record from null spell");
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
            StableKey = StableKeyGenerator.ForSpell(spell),
            SpellDBIndex = spellDbIndex,
            Id = spell.Id,
            SpellName = spell.SpellName,
            SpellDesc = spell.SpellDesc,
            SpecialDescriptor = spell.SpecialDescriptor,
            Type = spell.Type.ToString(),
            Line = spell.Line.ToString(),

            // --- Requirements & Cost ---
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
            // DISABLED: InflictOnSelf only exists in playtest variant
            // InflictOnSelf = spell.InflictOnSelf,

            // --- Core Effects (Damage/Heal/Shield) ---
            TargetDamage = spell.TargetDamage,
            TargetHealing = spell.TargetHealing,
            CasterHealing = spell.CasterHealing,
            ShieldingAmt = spell.ShieldingAmt,
            Lifetap = spell.Lifetap,
            DamageType = spell.MyDamageType.ToString(),
            ResistModifier = spell.ResistModifier,
            AddProcStableKey = spell.AddProc != null
                ? StableKeyGenerator.ForSpell(spell.AddProc)
                : null,
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
            // DISABLED: FearTarget only exists in playtest variant
            // FearTarget = spell.FearTarget,
            CrowdControlSpell = spell.CrowdControlSpell,
            BreakOnDamage = spell.BreakOnDamage,
            BreakOnAnyAction = spell.BreakOnAnyAction,
            TauntSpell = spell.TauntSpell,

            // --- Special Mechanics ---
            PetToSummonStableKey = spell.PetToSummon != null
                ? StableKeyGenerator.ForCharacter(spell.PetToSummon.GetComponent<Character>())
                : null,
            StatusEffectToApplyStableKey = spell.StatusEffectToApply != null
                ? StableKeyGenerator.ForSpell(spell.StatusEffectToApply)
                : null,
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

    private List<SpellClassRecord> CreateSpellClassRecords(Spell spell)
    {
        var records = new List<SpellClassRecord>();

        if (spell.UsedBy is { Count: > 0 })
        {
            var spellStableKey = StableKeyGenerator.ForSpell(spell);
            foreach (var characterClass in spell.UsedBy)
            {
                if (characterClass != null && !string.IsNullOrEmpty(characterClass.ClassName))
                {
                    records.Add(new SpellClassRecord
                    {
                        SpellStableKey = spellStableKey,
                        ClassName = characterClass.ClassName
                    });
                }
            }
        }

        return records;
    }
}
