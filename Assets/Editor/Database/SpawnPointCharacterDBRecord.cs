using SQLite;

[Table("SpawnPointCharacters")]
public class SpawnPointCharacterDBRecord
{
    [Indexed(Name = "SpawnPointCharacters_Primary_IDX", Order = 1, Unique = true)]
    public int SpawnPointId { get; set; }
    [Indexed(Name = "SpawnPointCharacters_Primary_IDX", Order = 2, Unique = true)]
    public string CharacterPrefabGuid { get; set; }
    public float SpawnChance { get; set; }
    public bool IsCommon { get; set; }
    public bool IsRare { get; set; }
    public bool IsUnique { get; set; }
}
