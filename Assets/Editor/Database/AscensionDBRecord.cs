#nullable enable

using SQLite;

[Table("Ascensions")]
public class AscensionDBRecord
{
    public int AscensionDBIndex { get; set; } // Index from the loaded Resources array
    [PrimaryKey]
    public string Id { get; set; } = string.Empty; // From BaseScriptableObject.Id

    public string UsedBy { get; set; } = string.Empty; // Store Ascension.Class enum as string
    public string SkillName { get; set; } = string.Empty;
    public string SkillDesc { get; set; } = string.Empty;
    public int MaxRank { get; set; }
    public int SimPlayerWeight { get; set; }

    // General Stats
    public float IncreaseHP { get; set; }
    public float IncreaseDEF { get; set; }
    public float IncreaseMana { get; set; }
    public float MR { get; set; }
    public float PR { get; set; }
    public float ER { get; set; }
    public float VR { get; set; }
    public float IncreaseDodge { get; set; }

    // Duelist Stats
    public float IncreaseCombatRoll { get; set; }
    public float DecreaseAggroGen { get; set; }
    public float ChanceForExtraAttack { get; set; }
    public float ChanceForDoubleBackstab { get; set; }
    public float ChanceToCritBackstab { get; set; }

    // Arcanist Stats
    public float ResistModIncrease { get; set; }
    public float DecreaseSpellAggroGen { get; set; }
    public float TripleResonateChance { get; set; }
    public float CooldownReduction { get; set; }
    public float IntelligenceScaling { get; set; }

    // Paladin Stats
    public float TripleAttackChance { get; set; }
    public float AggroGenIncrease { get; set; }
    public float MitigationIncrease { get; set; }
    public float AdvancedIncreaseHP { get; set; }
    public float AdvancedResists { get; set; }

    // Druid Stats
    public float HealingIncrease { get; set; }
    public float CriticalDotChance { get; set; }
    public float CriticalHealingChance { get; set; }
    public float VengefulHealingPercentage { get; set; }
    public float SummonedBeastEnhancement { get; set; }

    // Internals / Metadata
    public string ResourceName { get; set; } = string.Empty;
}
