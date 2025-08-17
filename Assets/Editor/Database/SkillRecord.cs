#nullable enable

using SQLite;

[Table("Skills")]
public class SkillRecord
{
    public const string TableName = "Skills";
    
    // --- Core Identification ---
    [PrimaryKey]
    public int SkillDBIndex { get; set; } // Index in the Resources.LoadAll array
    public string Id { get; set; } // From BaseScriptableObject.Id
    public string SkillName { get; set; } = string.Empty; // From Skill.SkillName
    public string SkillDesc { get; set; } = string.Empty; // From Skill.SkillDesc
    public string TypeOfSkill { get; set; } = string.Empty; // From Skill.TypeOfSkill enum as string

    // --- Timing & Cost ---
    public float Cooldown { get; set; } // From Skill.Cooldown

    // --- Requirements ---
    public int DuelistRequiredLevel { get; set; } // From Skill.DuelistRequiredLevel
    public int PaladinRequiredLevel { get; set; } // From Skill.PaladinRequiredLevel
    public int ArcanistRequiredLevel { get; set; } // From Skill.ArcanistRequiredLevel
    public int DruidRequiredLevel { get; set; } // From Skill.DruidRequiredLevel
    public int StormcallerRequiredLevel { get; set; } // From Skill.StormcallerRequiredLevel
    public bool RequireBehind { get; set; } // From Skill.RequireBehind
    public bool Require2H { get; set; } // From Skill.Require2H
    public bool RequireDW { get; set; } // From Skill.RequireDW
    public bool RequireBow { get; set; } // From Skill.RequireBow
    public bool RequireShield { get; set; } // From Skill.RequireShield

    // --- Simulation ---
    public bool SimPlayersAutolearn { get; set; } // From Skill.SimPlayersAutolearn

    // --- Effects & Mechanics ---
    public bool AESkill { get; set; } // From Skill.AESkill
    public bool Interrupt { get; set; } // From Skill.Interrupt
    public string SpawnOnUseResourceName { get; set; } = string.Empty; // From Skill.SpawnOnUse.name
    public string EffectToApplyId { get; set; } = string.Empty; // From Skill.EffectToApply.Id (Spell ID)
    public bool AffectPlayer { get; set; } // From Skill.AffectPlayer
    public bool AffectTarget { get; set; } // From Skill.AffectTarget
    public float SkillRange { get; set; } // From Skill.SkillRange
    public int SkillPower { get; set; } // From Skill.SkillPower
    public float PercentDmg { get; set; } // From Skill.PercentDmg
    public string DamageType { get; set; } = string.Empty; // From Skill.DmgType enum as string
    public bool ScaleOffWeapon { get; set; } // From Skill.ScaleOffWeapon
    public bool ProcWeap { get; set; } // From Skill.ProcWeap
    public bool ProcShield { get; set; } // From Skill.ProcShield
    public bool GuaranteeProc { get; set; } // From Skill.GuaranteeProc
    public bool AutomateAttack { get; set; } // From Skill.AutomateAttack
    public string CastOnTargetId { get; set; } = string.Empty; // From Skill.CastOnTarget (Spell name and ID)

    // --- Visual/Audio ---
    public string SkillAnimName { get; set; } = string.Empty; // From Skill.SkillAnimName
    public string? SkillIconName { get; set; } = string.Empty; // From Skill.SkillIcon.name
    
    // --- Text ---
    public string PlayerUses { get; set; } = string.Empty; // From Skill.PlayerUses
    public string NPCUses { get; set; } = string.Empty; // From Skill.NPCUses

    // --- Internals ---
    public string ResourceName { get; set; } = string.Empty; // From Skill.name (ScriptableObject name)
}
