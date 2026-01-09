#nullable enable

using SQLite;

[Table("Characters")]
public class CharacterRecord
{
    public const string TableName = "Characters";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty; // Stable identifier: "character:object_name" or "character:object_name|scene|x|y|z"
    [Indexed]
    public int? CoordinateId { get; set; }

    public string Guid { get; set; } = string.Empty; // Unity GUID (internal use only)
    public string? ObjectName { get; set; } = string.Empty;
    public string NPCName { get; set; } = string.Empty;

    public string? MyWorldFactionStableKey { get; set; } = string.Empty;
    public string MyFaction { get; set; } = string.Empty;
    public float AggroRange { get; set; }
    public float AttackRange { get; set; }
    public string? AggressiveTowards { get; set; } = string.Empty;
    public string? Allies { get; set; } = string.Empty;
    
    public bool IsPrefab { get; set; }
    public bool IsCommon { get; set; }
    public bool IsRare { get; set; }
    public bool IsUnique { get; set; }
    public bool IsFriendly { get; set; }
    public bool IsNPC { get; set; }
    public bool IsSimPlayer { get; set; }
    public bool IsVendor { get; set; }
    public bool IsMiningNode { get; set; }
    public bool HasStats { get; set; }
    public bool HasDialog { get; set; }
    public bool HasModifyFaction { get; set; }
    
    public bool IsEnabled { get; set; }
    public bool Invulnerable { get; set; }
    public string? ShoutOnDeath { get; set; } = string.Empty;
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string? QuestCompleteOnDeath { get; set; } = string.Empty;
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string? ShoutTriggerQuestStableKey { get; set; } = string.Empty;
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
    
    // Calculated/Effective Stats for NPCs
    public int EffectiveHP { get; set; }
    public int EffectiveAC { get; set; }
    public int EffectiveBaseAtkDmg { get; set; }
    public float EffectiveAttackAbility { get; set; }
    public int EffectiveMinMR { get; set; }
    public int EffectiveMaxMR { get; set; }
    public int EffectiveMinER { get; set; }
    public int EffectiveMaxER { get; set; }
    public int EffectiveMinPR { get; set; }
    public int EffectiveMaxPR { get; set; }
    public int EffectiveMinVR { get; set; }
    public int EffectiveMaxVR { get; set; }
    
    // NPC properties
    // Spells and skills are stored in junction tables:
    // - CharacterAttackSkillRecord
    // - CharacterAttackSpellRecord, CharacterBuffSpellRecord, CharacterHealSpellRecord
    // - CharacterGroupHealSpellRecord, CharacterCCSpellRecord, CharacterTauntSpellRecord

    [ForeignKey(typeof(SpellRecord), "StableKey")]
    public string? PetSpellStableKey { get; set; }
    [ForeignKey(typeof(SpellRecord), "StableKey")]
    public string? ProcOnHitStableKey { get; set; }
    public float ProcOnHitChance { get; set; }
    
    // NPC Combat Mechanics
    public bool HandSetResistances { get; set; }
    public int HardSetAC { get; set; }
    public int BaseAtkDmg { get; set; }
    public int OHAtkDmg { get; set; }
    public int MinAtkDmg { get; set; }
    public float DamageRangeMin { get; set; }
    public float DamageRangeMax { get; set; }
    public float DamageMult { get; set; }
    public float ArmorPenMult { get; set; }
    
    // Special Abilities
    public int PowerAttackBaseDmg { get; set; }
    public float PowerAttackFreq { get; set; }
    public float HealTolerance { get; set; }
    
    // AI Behavior
    public float LeashRange { get; set; }
    public bool AggroRegardlessOfLevel { get; set; }
    public bool Mobile { get; set; }
    public bool GroupEncounter { get; set; }
    
    // Loot/Corpse
    public bool TreasureChest { get; set; }
    public bool DoNotLeaveCorpse { get; set; }
    
    // Achievements
    public string SetAchievementOnDefeat { get; set; } = string.Empty;
    public string SetAchievementOnSpawn { get; set; } = string.Empty;
    
    // Flavor Text
    public string AggroMsg { get; set; } = string.Empty;
    public string AggroEmote { get; set; } = string.Empty;
    public string SpawnEmote { get; set; } = string.Empty;
    public string GuildName { get; set; } = string.Empty;
    
    // ModifyFaction properties
    public string ModifyFactions { get; set; } = string.Empty;
    
    // VendorInventory properties
    public string VendorDesc { get; set; } = string.Empty;
    public string? ItemsForSale { get; set; } = string.Empty;

    // QuestManager properties
    public bool QuestManagerSimUsable { get; set; }
}
