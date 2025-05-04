using SQLite;

[Table("SpawnPointCharacters")]
public class SpawnPointCharacterDBRecord
{
    [PrimaryKey]
    public string SpawnPointId { get; set; } // Foreign key to SpawnPoints.Id

    [Indexed]
    public string CharacterPrefabGuid { get; set; } // Foreign key to Characters.PrefabGuid

    [PrimaryKey]
    public string SpawnType { get; set; } // e.g., "Common", "Rare"
    [PrimaryKey]
    public int SpawnListIndex { get; set; } // Index within the SpawnPoint's list

    // Calculated probability of this specific character spawning (0.0 to 1.0)
    public float SpawnChance { get; set; }
}
