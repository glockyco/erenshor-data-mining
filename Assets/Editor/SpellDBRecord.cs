using SQLite;
using UnityEngine; // Needed for Color

[Table("Spells")]
public class SpellDBRecord
{
    [PrimaryKey]
    public string Id { get; set; } // From BaseScriptableObject.Id
    public string SpellName { get; set; } // From Spell.SpellName
    public string Type { get; set; } // From Spell.Type enum
    public string Line { get; set; } // From Spell.Line enum
    public int RequiredLevel { get; set; } // From Spell.RequiredLevel
    public int SpellChargeFXIndex { get; set; } // From Spell.SpellChargeFXIndex
    public int SpellResolveFXIndex { get; set; } // From Spell.SpellResolveFXIndex
    public float SpellChargeTime { get; set; } // From Spell.SpellChargeTime
    public string SpellIconName { get; set; } // From Spell.SpellIcon.name
    public int SpellDurationInTicks { get; set; } // From Spell.SpellDurationInTicks
    public bool UnstableDuration { get; set; } // From Spell.UnstableDuration
    public string StatusEffectMessageOnPlayer { get; set; } // From Spell.StatusEffectMessageOnPlayer
    public string StatusEffectMessageOnNPC { get; set; } // From Spell.StatusEffectMessageOnNPC
    public string SpellDesc { get; set; } // From Spell.SpellDesc
    public bool InstantEffect { get; set; } // From Spell.InstantEffect
    public int ManaCost { get; set; } // From Spell.ManaCost
    public int Aggro { get; set; } // From Spell.Aggro
    public int TargetDamage { get; set; } // From Spell.TargetDamage
    public int TargetHealing { get; set; } // From Spell.TargetHealing
    public int CasterHealing { get; set; } // From Spell.CasterHealing
    public float Cooldown { get; set; } // From Spell.Cooldown
    public int ShieldingAmt { get; set; } // From Spell.ShieldingAmt
    public int HP { get; set; } // Stat buff from Spell.HP
    public int AC { get; set; } // Stat buff from Spell.AC
    public int Mana { get; set; } // Stat buff from Spell.Mana
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
    public bool RootTarget { get; set; } // From Spell.RootTarget
    public bool StunTarget { get; set; } // From Spell.StunTarget
    public bool CharmTarget { get; set; } // From Spell.CharmTarget
    public bool Lifetap { get; set; } // From Spell.Lifetap
    public bool GroupEffect { get; set; } // From Spell.GroupEffect
    public string DamageType { get; set; } // From Spell.MyDamageType enum
    public float ResistModifier { get; set; } // From Spell.ResistModifier
    public float SpellRange { get; set; } // From Spell.SpellRange
    public bool SelfOnly { get; set; } // From Spell.SelfOnly
    public int MaxLevelTarget { get; set; } // From Spell.MaxLevelTarget
    public string PetToSummonResourceName { get; set; } // From Spell.PetToSummon.name
    public string StatusEffectToApplyId { get; set; } // From Spell.StatusEffectToApply.Id
    public bool ApplyToCaster { get; set; } // From Spell.ApplyToCaster
    public float ShakeDur { get; set; } // From Spell.ShakeDur
    public float ShakeAmp { get; set; } // From Spell.ShakeAmp
    public float ColorR { get; set; } // From Spell.color.r
    public float ColorG { get; set; } // From Spell.color.g
    public float ColorB { get; set; } // From Spell.color.b
    public float ColorA { get; set; } // From Spell.color.a
    public bool SimUsable { get; set; } // From Spell.SimUsable
    public bool CanHitPlayers { get; set; } // From Spell.CanHitPlayers
    public bool BreakOnDamage { get; set; } // From Spell.BreakOnDamage
    public bool CrowdControlSpell { get; set; } // From Spell.CrowdControlSpell
    public bool TauntSpell { get; set; } // From Spell.TauntSpell
    public bool ReapAndRenew { get; set; } // From Spell.ReapAndRenew
    public int ResonateChance { get; set; } // From Spell.ResonateChance
    public float XPBonus { get; set; } // From Spell.XPBonus
    public bool AutomateAttack { get; set; } // From Spell.AutomateAttack
    public string Classes { get; set; } // Comma-separated list from Spell.UsedBy
    public string ResourceName { get; set; } // From Spell.name (ScriptableObject name)
}
