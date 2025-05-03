using SQLite;
using UnityEngine; // Needed for Vector3

[Table("SpawnPoints")]
public class SpawnPointDBRecord
{
    [PrimaryKey]
    public string Id { get; set; } // Using SpawnPoint.ID (SceneName + Position)

    public string SceneName { get; set; }
    public float PositionX { get; set; }
    public float PositionY { get; set; }
    public float PositionZ { get; set; }
    public int RareNPCChance { get; set; }
    public int LevelMod { get; set; }
    public float SpawnDelay { get; set; }
    public bool Staggerable { get; set; } // Stored as 0 or 1
    public float StaggerMod { get; set; }
    public bool NightSpawn { get; set; } // Stored as 0 or 1
    public string PatrolPoints { get; set; } // Comma-separated list of Transform.ToString() coordinates
    public bool LoopPatrol { get; set; } // Stored as 0 or 1
    public float RandomWanderRange { get; set; }
    public string SpawnUponQuestCompleteDBName { get; set; } // Nullable
    public string StopIfQuestCompleteDBNames { get; set; } // Nullable, comma-separated
    public string ProtectorName { get; set; } // Nullable


    // Helper to set position easily
    public void SetPosition(Vector3 position)
    {
        PositionX = position.x;
        PositionY = position.y;
        PositionZ = position.z;
    }
}
