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
    public float RotationY { get; set; }
    public float SpawnDelay { get; set; }
    public int RareNPCChance { get; set; }
    public int LevelMod { get; set; }
    public float RandomWanderRange { get; set; }
    public bool LoopPatrol { get; set; } // Stored as 0 or 1
    public bool NightSpawn { get; set; } // Stored as 0 or 1
    public string SpawnUponQuestCompleteQuestDBName { get; set; } // Nullable
    public string StopIfQuestCompleteQuestDBNames { get; set; } // Nullable, comma-separated
    public string ProtectorName { get; set; } // Nullable
    public bool Staggerable { get; set; } // Stored as 0 or 1
    public float StaggerMod { get; set; }

    public string PatrolPoints { get; set; } // Comma-separated list of Transform.ToString() coordinates

    // Helper to set position easily
    public void SetPosition(Vector3 position)
    {
        PositionX = position.x;
        PositionY = position.y;
        PositionZ = position.z;
    }
}
