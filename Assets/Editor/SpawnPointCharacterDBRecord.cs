using SQLite;

[Table("SpawnPointCharacters")]
public class SpawnPointCharacterDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }

    [Indexed]
    public string SpawnPointId { get; set; } // Foreign key to SpawnPoints.Id

    [Indexed]
    public string CharacterPrefabGuid { get; set; } // Foreign key to Characters.PrefabGuid

    public string SpawnType { get; set; } // e.g., "Common", "Rare"
    public int SpawnListIndex { get; set; } // Index within the SpawnPoint's list
}
