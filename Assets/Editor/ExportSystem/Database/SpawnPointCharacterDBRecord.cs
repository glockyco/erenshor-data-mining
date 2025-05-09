using SQLite;

[Table("SpawnPointCharacters")]
public class SpawnPointCharacterDBRecord
{
    [Indexed(Name = "SpawnPointCharacters_Primary_IDX", Order = 1, Unique = true)]
    public string SpawnPointId { get; set; } // Foreign key to SpawnPoints.Id

    [Indexed]
    public string CharacterPrefabGuid { get; set; } // Foreign key to Characters.PrefabGuid

    [Indexed(Name = "SpawnPointCharacters_Primary_IDX", Order = 2, Unique = true)]
    public string SpawnType { get; set; } // e.g., "Common", "Rare"
    [Indexed(Name = "SpawnPointCharacters_Primary_IDX", Order = 3, Unique = true)]
    public int SpawnListIndex { get; set; } // Index within the SpawnPoint's list

    // Calculated probability of this specific character spawning (0.0 to 1.0)
    public float SpawnChance { get; set; }
}
