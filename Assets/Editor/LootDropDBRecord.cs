using SQLite;

[Table("LootDrops")]
public class LootDropDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }

    [Indexed]
    public string CharacterPrefabGuid { get; set; }

    [Indexed]
    public string ItemId { get; set; }

    public string DropType { get; set; }
    public int DropIndex { get; set; }
}