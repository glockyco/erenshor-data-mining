#nullable enable

using SQLite;

[Table("ItemStats")]
public class ItemStatsRecord
{
    public const string TableName = "ItemStats";
    
    [Indexed(Name = "ItemStats_Primary_IDX", Order = 1, Unique = true)]
    public string ItemResourceName { get; set; } = string.Empty;
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
    
    // --- Stat Scaling Properties ---
    public float StrScaling { get; set; }
    public float EndScaling { get; set; }
    public float DexScaling { get; set; }
    public float AgiScaling { get; set; }
    public float IntScaling { get; set; }
    public float WisScaling { get; set; }
    public float ChaScaling { get; set; }
    public float ResistScaling { get; set; }
    public float MitigationScaling { get; set; }

    public string WikiString { get; set; } = string.Empty;
}
