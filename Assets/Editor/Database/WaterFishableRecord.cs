using SQLite;

[Table("WaterFishables")]
public class WaterFishableDBRecord
{
    [Indexed(Name = "WaterFishable_Primary_IDX", Order = 1, Unique = true)]
    public int WaterId { get; set; }
    [Indexed(Name = "WaterFishable_Primary_IDX", Order = 2, Unique = true)]
    public string Type { get; set; } // "DayFishable" or "NightFishable"
    [Indexed(Name = "WaterFishable_Primary_IDX", Order = 3, Unique = true)]
    public string ItemName { get; set; }
    public float DropChance { get; set; }
}