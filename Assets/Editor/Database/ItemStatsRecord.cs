#nullable enable

using SQLite;

[Table("ItemStats")]
public class ItemStatsRecord
{
    public const string TableName = "ItemStats";
    
    [Indexed(Name = "ItemStats_Primary_IDX", Order = 1, Unique = true)]
    public string ItemId { get; set; } = string.Empty;
    [Indexed(Name = "ItemStats_Primary_IDX", Order = 2, Unique = true)]
    public string Quality { get; set; } = string.Empty; // "Normal", "Blessed", "Godly"
    
    public int WeaponDmg { get; set; }
    
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

    public string WikiString { get; set; } = string.Empty;
}
