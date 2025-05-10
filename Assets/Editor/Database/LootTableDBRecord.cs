using SQLite;

[Table("LootDrops")]
public class LootTableDBRecord
{
    [Indexed(Name = "LootDrops_Primary_IDX", Order = 1, Unique = true)]
    public string CharacterPrefabGuid { get; set; }

    [Indexed]
    public string ItemId { get; set; }

    [Indexed(Name = "LootDrops_Primary_IDX", Order = 2, Unique = true)]
    public string DropType { get; set; }
    [Indexed(Name = "LootDrops_Primary_IDX", Order = 3, Unique = true)]
    public int DropIndex { get; set; }
    public double Probability { get; set; }
}