using SQLite;

[Table("LootDrops")]
public class LootDropDBRecord
{
    [PrimaryKey]
    public string CharacterPrefabGuid { get; set; }

    [Indexed]
    public string ItemId { get; set; }

    [PrimaryKey]
    public string DropType { get; set; }
    [PrimaryKey]
    public int DropIndex { get; set; }
    public double Probability { get; set; }
}