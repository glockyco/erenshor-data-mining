using SQLite;

[Table("WaterFishables")]
public class WaterFishableDBRecord
{
    [Indexed(Name = "WaterFishable_Primary_IDX", Order = 1, Unique = true)]
    public string WaterId { get; set; } // SceneName(WaterIndex)
    [Indexed(Name = "WaterFishable_Primary_IDX", Order = 2, Unique = true)]
    public string Type { get; set; } // "DayFishable" or "NightFishable"
    [Indexed(Name = "WaterFishable_Primary_IDX", Order = 3, Unique = true)]
    public int Index { get; set; }
    
    public string ItemId { get; set; }
    public string ItemName { get; set; }
    public float DropChance { get; set; } // Probability of this entry dropping (0.0 to 100.0)
    public float TotalDropChance { get; set; } // Probability of this item dropping (0.0 to 100.0)
}