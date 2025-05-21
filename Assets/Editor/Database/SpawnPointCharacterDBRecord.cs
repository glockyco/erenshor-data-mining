using SQLite;

[Table("SpawnPointCharacters")]
public class SpawnPointCharacterDBRecord
{
    [Indexed(Name = "SpawnPointCharacters_Primary_IDX", Order = 1, Unique = true)]
    public string SpawnPointId { get; set; }

    [Indexed]
    public string CharacterPrefabGuid { get; set; }

    [Indexed(Name = "SpawnPointCharacters_Primary_IDX", Order = 2, Unique = true)]
    public string SpawnType { get; set; }
    [Indexed(Name = "SpawnPointCharacters_Primary_IDX", Order = 3, Unique = true)]
    public int SpawnListIndex { get; set; }

    public float SpawnChance { get; set; }
    public float TotalSpawnChance { get; set; }
}
