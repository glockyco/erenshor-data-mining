#nullable enable

using SQLite;

[Table("Items")]
public class ItemRecord
{
    public const string TableName = "Items";
    
    // --- Core Identification ---
    public int ItemDBIndex { get; set; } // Index in the Resources.LoadAll<Item> array
    [Indexed]
    public string Id { get; set; } = string.Empty;
    public string ItemName { get; set; } = string.Empty;
    public string Lore { get; set; } = string.Empty;

    // --- Classification & Requirements ---
    public string RequiredSlot { get; set; } = string.Empty; // From Item.SlotType enum
    public string ThisWeaponType { get; set; } = string.Empty; // From Item.WeaponType enum
    public string Classes { get; set; } = string.Empty; // Comma-separated list from Item.Classes
    public int ItemLevel { get; set; }

    // --- Weapon/Combat Properties ---
    public float WeaponDly { get; set; }
    public bool Shield { get; set; } // Is it a shield?
    public float WeaponProcChance { get; set; }
    public string WeaponProcOnHit { get; set; } = string.Empty; // Spell ResourceName

    // --- Wand Properties ---
    public bool IsWand { get; set; }
    public int WandRange { get; set; }
    public float WandProcChance { get; set; }
    public string WandEffect { get; set; } = string.Empty; // Spell ResourceName
    public float WandBoltColorR { get; set; }
    public float WandBoltColorG { get; set; }
    public float WandBoltColorB { get; set; }
    public float WandBoltColorA { get; set; }
    public float WandBoltSpeed { get; set; }
    public string? WandAttackSoundName { get; set; } = string.Empty;

    // --- Bow Properties ---
    public bool IsBow { get; set; }
    public string BowEffect { get; set; } = string.Empty; // Spell ResourceName
    public float BowProcChance { get; set; }
    public int BowRange { get; set; }
    public float BowArrowSpeed { get; set; }
    public string? BowAttackSoundName { get; set; } = string.Empty;

    // --- Effects & Interactions ---
    public string ItemEffectOnClick { get; set; } = string.Empty; // Spell ResourceName
    public string ItemSkillUse { get; set; } = string.Empty; // Skill ResourceName
    public string TeachSpell { get; set; } = string.Empty; // Spell ResourceName
    public string TeachSkill { get; set; } = string.Empty; // Skill ResourceName
    public string Aura { get; set; } = string.Empty; // Spell ResourceName
    public string WornEffect { get; set; } = string.Empty; // Spell ResourceName
    public float SpellCastTime { get; set; } // Cast time modifier or specific cast time? (Check Item.cs usage)

    // --- Quest Interaction ---
    public string? AssignQuestOnRead { get; set; } = string.Empty; // Quest assigned on read
    public string? CompleteOnRead { get; set; } = string.Empty; // Quest completed on read

    // --- Crafting & Templates ---
    public bool Template { get; set; }
    public string TemplateIngredientIds { get; set; } = string.Empty; // Comma-separated list of Item Ids
    public string TemplateRewardIds { get; set; } = string.Empty; // Comma-separated list of Item Ids

    // --- Economy & Inventory ---
    public int ItemValue { get; set; } // Gold value
    public int SellValue { get; set; } // Gold value when sold to a vendor
    public bool Stackable { get; set; }
    public bool Disposable { get; set; }
    public bool Unique { get; set; }
    public bool Relic { get; set; }
    public bool NoTradeNoDestroy { get; set; }

    // --- Miscellaneous ---
    public string BookTitle { get; set; } = string.Empty; // If the item is a book
    public int Mining { get; set; } // Mining skill required/provided? (Check Item.cs usage)
    public bool FuelSource { get; set; }
    public int FuelLevel { get; set; } // From Item.FuelTier enum
    public bool SimPlayersCantGet { get; set; } // Flag for simulation behavior
    
    // --- Visuals & Sound ---
    public string? AttackSoundName { get; set; } = string.Empty; // Name of the AudioClip
    public string? ItemIconName { get; set; } = string.Empty; // Name of the Sprite for the icon
    public string EquipmentToActivate { get; set; } = string.Empty; // String identifier for visual equipment
    //public string ShoulderTrimL { get; set; }
    //public string ShoulderTrimR { get; set; }
    //public string ElbowTrimL { get; set; }
    //public string ElbowTrimR { get; set; }
    //public string KneeTrimL { get; set; }
    //public string KneeTrimR { get; set; }
    public bool HideHairWhenEquipped { get; set; }
    public bool HideHeadWhenEquipped { get; set; }
    // Colors (RGBA components)
    //public float ItemPrimaryColorR { get; set; }
    //public float ItemPrimaryColorG { get; set; }
    //public float ItemPrimaryColorB { get; set; }
    //public float ItemPrimaryColorA { get; set; }
    //public float ItemSecondaryColorR { get; set; }
    //public float ItemSecondaryColorG { get; set; }
    //public float ItemSecondaryColorB { get; set; }
    //public float ItemSecondaryColorA { get; set; }
    //public float ItemMetalPrimaryR { get; set; }
    //public float ItemMetalPrimaryG { get; set; }
    //public float ItemMetalPrimaryB { get; set; }
    //public float ItemMetalPrimaryA { get; set; }
    //public float ItemLeatherPrimaryR { get; set; }
    //public float ItemLeatherPrimaryG { get; set; }
    //public float ItemLeatherPrimaryB { get; set; }
    //public float ItemLeatherPrimaryA { get; set; }
    //public float ItemMetalDarkR { get; set; }
    //public float ItemMetalDarkG { get; set; }
    //public float ItemMetalDarkB { get; set; }
    //public float ItemMetalDarkA { get; set; }
    //public float ItemMetalSecondaryR { get; set; }
    //public float ItemMetalSecondaryG { get; set; }
    //public float ItemMetalSecondaryB { get; set; }
    //public float ItemMetalSecondaryA { get; set; }
    //public float ItemLeatherSecondaryR { get; set; }
    //public float ItemLeatherSecondaryG { get; set; }
    //public float ItemLeatherSecondaryB { get; set; }
    //public float ItemLeatherSecondaryA { get; set; }

    // --- Internal ---
    [PrimaryKey]
    public string ResourceName { get; set; } = string.Empty; // Original Item.name (ScriptableObject filename)
}
