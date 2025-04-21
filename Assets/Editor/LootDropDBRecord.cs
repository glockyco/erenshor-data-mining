using SQLite;

public class LootDropDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    
    [Indexed]
    public string CharacterPrefabGuid { get; set; }  // Foreign key to CharacterDBRecord.PrefabGuid
    
    [Indexed]
    public string ItemId { get; set; }  // Foreign key to ItemDBRecord.Id
    
    public string DropType { get; set; }  // "Guaranteed", "Common", "Uncommon", "Rare", "Legendary"
    
    public int DropIndex { get; set; }  // Index in the original list
}