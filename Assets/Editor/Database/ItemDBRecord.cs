using SQLite;

[Table("Items")]
public class ItemDBRecord
{
    // --- Core Identification ---
    public int ItemDBIndex { get; set; } // Index in the Resources.LoadAll<Item> array
    [PrimaryKey]
    public string Id { get; set; } // Composite ID like "BaseID_q1", "BaseID_q2", etc.
    public string BaseItemId { get; set; } // Original Item.Id
    public string ItemName { get; set; }
    public string Lore { get; set; }

    // --- Classification & Requirements ---
    public string RequiredSlot { get; set; } // From Item.SlotType enum
    public string ThisWeaponType { get; set; } // From Item.WeaponType enum
    public string Classes { get; set; } // Comma-separated list from Item.Classes
    public string Quality { get; set; } // "Normal", "Blessed", "Godly"
    public int ItemLevel { get; set; }

    // --- Core Stats (Affected by Quality) ---
    public int HP { get; set; }
    public int AC { get; set; }
    public int Mana { get; set; }
    public int Str { get; set; }
    public int End { get; set; }
    public int Dex { get; set; }
    public int Agi { get; set; }
    public int Int { get; set; }
    public int Wis { get; set; }
    public int Cha { get; set; }
    public int Res { get; set; } // Resonance
    public int MR { get; set; } // Magic Resist
    public int ER { get; set; } // Elemental Resist
    public int PR { get; set; } // Poison Resist
    public int VR { get; set; } // Void Resist

    // --- Weapon/Combat Properties ---
    public int WeaponDmg { get; set; }
    public float WeaponDly { get; set; }
    public bool Shield { get; set; } // Is it a shield?
    public float WeaponProcChance { get; set; }
    public string WeaponProcOnHitId { get; set; } // Id of the Spell to proc

    // --- Effects & Interactions ---
    public string ItemEffectOnClickId { get; set; } // Id of the Spell to cast on click
    public string ItemSkillUseId { get; set; } // Id of the Skill to use on click
    public string TeachSpellId { get; set; } // Id of the Spell taught by this item
    public string TeachSkillId { get; set; } // Id of the Skill taught by this item
    public string AuraId { get; set; } // Id of the Spell providing a passive aura
    public string WornEffectId { get; set; } // Id of the Spell providing a passive worn effect
    public float SpellCastTime { get; set; } // Cast time modifier or specific cast time? (Check Item.cs usage)

    // --- Quest Interaction ---
    public string AssignQuestOnRead { get; set; } // Quest assigned on read
    public string CompleteOnRead { get; set; } // Quest completed on read

    // --- Crafting & Templates ---
    public bool Template { get; set; }
    public string TemplateIngredientIds { get; set; } // Comma-separated list of Item Ids
    public string TemplateRewardIds { get; set; } // Comma-separated list of Item Ids

    // --- Economy & Inventory ---
    public int ItemValue { get; set; } // Gold value
    public int SellValue { get; set; } // Gold value when sold to a vendor
    public bool Stackable { get; set; }
    public bool Disposable { get; set; }
    public bool Unique { get; set; }
    public bool Relic { get; set; }

    // --- Miscellaneous ---
    public string BookTitle { get; set; } // If the item is a book
    public int Mining { get; set; } // Mining skill required/provided? (Check Item.cs usage)
    public bool FuelSource { get; set; }
    public int FuelLevel { get; set; } // From Item.FuelTier enum
    public bool SimPlayersCantGet { get; set; } // Flag for simulation behavior
    
    // --- Visuals & Sound ---
    public string AttackSoundName { get; set; } // Name of the AudioClip
    public string ItemIconName { get; set; } // Name of the Sprite for the icon
    public string EquipmentToActivate { get; set; } // String identifier for visual equipment
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
    public string ResourceName { get; set; } // Original Item.name (ScriptableObject filename)

    // --- Wiki ---
    public string WikiString { get; set; } // Generated wiki string for this item
}
