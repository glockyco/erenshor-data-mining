#nullable enable

using SQLite;

[Table("Characters")]
public class CharacterDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int? CoordinateId { get; set; }

    public string Guid { get; set; } = string.Empty;
    public string ObjectName { get; set; } = string.Empty;
    public string NPCName { get; set; } = string.Empty;

    public string MyWorldFaction { get; set; } = string.Empty;
    public string MyFaction { get; set; } = string.Empty;
    public float AggroRange { get; set; }
    public float AttackRange { get; set; }
    public string AggressiveTowards { get; set; } = string.Empty;
    public string Allies { get; set; } = string.Empty;
    
    public bool IsNPC { get; set; }
    public bool IsSimPlayer { get; set; }
    public bool IsVendor { get; set; }
    public bool IsMiningNode { get; set; }
    public bool HasStats { get; set; }
    public bool HasDialog { get; set; }
    public bool HasModifyFaction { get; set; }
    
    public bool IsEnabled { get; set; }
    public bool Invulnerable { get; set; }
    public string ShoutOnDeath { get; set; } = string.Empty;
    public string QuestCompleteOnDeath { get; set; } = string.Empty;
    public bool DestroyOnDeath { get; set; }

    // Stats properties
    public int Level { get; set; }
    public float BaseXpMin { get; set; } 
    public float BaseXpMax { get; set; } 
    public float BossXpMultiplier { get; set; }
    public int BaseHP { get; set; }
    public int BaseAC { get; set; }
    public int BaseMana { get; set; }
    public int BaseStr { get; set; }
    public int BaseEnd { get; set; }
    public int BaseDex { get; set; }
    public int BaseAgi { get; set; }
    public int BaseInt { get; set; }
    public int BaseWis { get; set; }
    public int BaseCha { get; set; }
    public int BaseRes { get; set; }
    public int BaseMR { get; set; }
    public int BaseER { get; set; }
    public int BasePR { get; set; }
    public int BaseVR { get; set; }
    public float RunSpeed { get; set; }
    public float BaseLifeSteal { get; set; }
    public float BaseMHAtkDelay { get; set; }
    public float BaseOHAtkDelay { get; set; }
    
    // NPC properties
    public string AttackSkills { get; set; } = string.Empty;
    public string AttackSpells { get; set; } = string.Empty;
    public string BuffSpells { get; set; } = string.Empty;
    public string HealSpells { get; set; } = string.Empty;
    public string GroupHealSpells { get; set; } = string.Empty;
    public string CCSpells { get; set; } = string.Empty;
    public string TauntSpells { get; set; } = string.Empty;
    public string PetSpell { get; set; } = string.Empty;
    public string ProcOnHit { get; set; } = string.Empty;
    public float ProcOnHitChance { get; set; }
    
    // ModifyFaction properties
    public string ModifyFactions { get; set; } = string.Empty;
    
    // VendorInventory properties
    public string VendorDesc { get; set; } = string.Empty;
    public string ItemsForSale { get; set; } = string.Empty;
}
