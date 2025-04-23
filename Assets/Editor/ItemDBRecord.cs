using SQLite;

[Table("Items")]
public class ItemDBRecord
{
    [PrimaryKey]
    public string Id { get; set; } // Will be like "BaseID_q1", "BaseID_q2", etc.
    public string BaseItemId { get; set; } // Stores the original Item.Id
    public int Quality { get; set; } // Stores the quality level (1, 2, or 3)
    public string ResourceName { get; set; }
    public string ItemName { get; set; }
    public int ItemLevel { get; set; }
    public int HP { get; set; }
    public int AC { get; set; }
    public int Mana { get; set; }
    public int WeaponDmg { get; set; }
    public float WeaponDly { get; set; }
    public int Str { get; set; }
    public int End { get; set; }
    public int Dex { get; set; }
    public int Agi { get; set; }
    public int Int { get; set; }
    public int Wis { get; set; }
    public int Cha { get; set; }
    public int Res { get; set; }
    public int MR { get; set; }
    public int ER { get; set; }
    public int PR { get; set; }
    public int VR { get; set; }
    public int RequiredSlot { get; set; }
    public int ThisWeaponType { get; set; }
    public int ItemValue { get; set; }
    public string Lore { get; set; }
    public bool Shield { get; set; }
    public float WeaponProcChance { get; set; }
    public float SpellCastTime { get; set; }
    public bool HideHairWhenEquipped { get; set; }
    public bool HideHeadWhenEquipped { get; set; }
    public bool Stackable { get; set; }
    public bool Disposable { get; set; }
    public bool Unique { get; set; }
    public int Mining { get; set; }
    public bool FuelSource { get; set; }
    public bool Template { get; set; }
    public bool SimPlayersCantGet { get; set; }
    public int FuelLevel { get; set; }
    public bool Relic { get; set; }
    public string BookTitle { get; set; }
}
