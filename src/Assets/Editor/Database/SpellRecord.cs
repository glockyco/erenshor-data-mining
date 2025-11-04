#nullable enable

using SQLite;

[Table("Spells")]
public class SpellRecord
{
    public const string TableName = "Spells";
    
    // --- Core Identification ---
    public int SpellDBIndex { get; set; } // Index in the Resources.LoadAll array
    [Indexed]
    public string Id { get; set; } = string.Empty; // From BaseScriptableObject.Id
    public string SpellName { get; set; } = string.Empty; // From Spell.SpellName
    public string SpellDesc { get; set; } = string.Empty; // From Spell.SpellDesc
    public string SpecialDescriptor { get; set; } = string.Empty; // From Spell.SpecialDescriptor
    public string Type { get; set; } = string.Empty; // From Spell.Type enum
    public string Line { get; set; } = string.Empty; // From Spell.Line enum

    // --- Requirements & Cost ---
    public string Classes { get; set; } = string.Empty; // Comma-separated list from Spell.UsedBy
    public int RequiredLevel { get; set; } // From Spell.RequiredLevel
    public int ManaCost { get; set; } // From Spell.ManaCost

    // --- Simulation ---
    public bool SimUsable { get; set; } // From Spell.SimUsable
    
    // --- Aggro ---
    public int Aggro { get; set; } // From Spell.Aggro

    // --- Timing ---
    public float SpellChargeTime { get; set; } // From Spell.SpellChargeTime
    public float Cooldown { get; set; } // From Spell.Cooldown
    public int SpellDurationInTicks { get; set; } // From Spell.SpellDurationInTicks
    public bool UnstableDuration { get; set; } // From Spell.UnstableDuration
    public bool InstantEffect { get; set; } // From Spell.InstantEffect

    // --- Targeting ---
    public float SpellRange { get; set; } // From Spell.SpellRange
    public bool SelfOnly { get; set; } // From Spell.SelfOnly
    public int MaxLevelTarget { get; set; } // From Spell.MaxLevelTarget
    public bool GroupEffect { get; set; } // From Spell.GroupEffect
    public bool CanHitPlayers { get; set; } // From Spell.CanHitPlayers
    public bool ApplyToCaster { get; set; } // From Spell.ApplyToCaster

    // --- Core Effects (Damage/Heal/Shield) ---
    public int TargetDamage { get; set; } // From Spell.TargetDamage
    public int TargetHealing { get; set; } // From Spell.TargetHealing
    public int CasterHealing { get; set; } // From Spell.CasterHealing
    public int ShieldingAmt { get; set; } // From Spell.ShieldingAmt
    public bool Lifetap { get; set; } // From Spell.Lifetap
    public string DamageType { get; set; } // From Spell.MyDamageType enum
    public float ResistModifier { get; set; } // From Spell.ResistModifier
    public string AddProc { get; set; } = string.Empty; // Spell ID from Spell.AddProc
    public int AddProcChance { get; set; } // From Spell.AddProcChance

    // --- Stat Buffs/Debuffs ---
    public int HP { get; set; } // Stat buff from Spell.HP
    public int AC { get; set; } // Stat buff from Spell.AC
    public int Mana { get; set; } // Stat buff from Spell.Mana
    public int PercentManaRestoration { get; set; } // From Spell.PercentManaRestoration
    public float MovementSpeed { get; set; } // Stat buff from Spell.MovementSpeed
    public int Str { get; set; } // Stat buff from Spell.Str
    public int Dex { get; set; } // Stat buff from Spell.Dex
    public int End { get; set; } // Stat buff from Spell.End
    public int Agi { get; set; } // Stat buff from Spell.Agi
    public int Wis { get; set; } // Stat buff from Spell.Wis
    public int Int { get; set; } // Stat buff from Spell.Int
    public int Cha { get; set; } // Stat buff from Spell.Cha
    public int MR { get; set; } // Stat buff from Spell.MR
    public int ER { get; set; } // Stat buff from Spell.ER
    public int PR { get; set; } // Stat buff from Spell.PR
    public int VR { get; set; } // Stat buff from Spell.VR
    public int DamageShield { get; set; } // Stat buff from Spell.DamageShield
    public float Haste { get; set; } // Stat buff from Spell.Haste
    public float PercentLifesteal { get; set; } // Stat buff from Spell.percentLifesteal
    public int AtkRollModifier { get; set; } // From Spell.AtkRollModifier
    public int BleedDamagePercent { get; set; } // From Spell.BleedDamagePercent

    // --- Control Effects ---
    public bool RootTarget { get; set; } // From Spell.RootTarget
    public bool StunTarget { get; set; } // From Spell.StunTarget
    public bool CharmTarget { get; set; } // From Spell.CharmTarget
    public bool CrowdControlSpell { get; set; } // From Spell.CrowdControlSpell
    public bool BreakOnDamage { get; set; } // From Spell.BreakOnDamage
    public bool BreakOnAnyAction { get; set; } // From Spell.BreakOnAnyAction
    public bool TauntSpell { get; set; } // From Spell.TauntSpell

    // --- Special Mechanics ---
    public string PetToSummonResourceName { get; set; } = string.Empty; // From Spell.PetToSummon.name
    public string StatusEffectToApply { get; set; } = string.Empty; // Spell ID from Spell.StatusEffectToApply
    public bool ReapAndRenew { get; set; } // From Spell.ReapAndRenew
    public int ResonateChance { get; set; } // From Spell.ResonateChance
    public float XPBonus { get; set; } // From Spell.XPBonus
    public bool AutomateAttack { get; set; } // From Spell.AutomateAttack
    public bool WornEffect { get; set; } // From Spell.WornEffect

    // --- Visual/Audio ---
    public int SpellChargeFXIndex { get; set; } // From Spell.SpellChargeFXIndex
    public int SpellResolveFXIndex { get; set; } // From Spell.SpellResolveFXIndex
    public string? SpellIconName { get; set; } = string.Empty; // From Spell.SpellIcon.name
    public float ShakeDur { get; set; } // From Spell.ShakeDur
    public float ShakeAmp { get; set; } // From Spell.ShakeAmp
    public float ColorR { get; set; } // From Spell.color.r
    public float ColorG { get; set; } // From Spell.color.g
    public float ColorB { get; set; } // From Spell.color.b
    public float ColorA { get; set; } // From Spell.color.a

    // --- Text/Metadata ---
    public string StatusEffectMessageOnPlayer { get; set; } = string.Empty; // From Spell.StatusEffectMessageOnPlayer
    public string StatusEffectMessageOnNPC { get; set; } = string.Empty; // From Spell.StatusEffectMessageOnNPC
    
    // --- Internals ---
    [PrimaryKey]
    public string ResourceName { get; set; } = string.Empty; // From Spell.name (ScriptableObject name)
}
