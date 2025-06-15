#nullable enable

using SQLite;

[Table("SpawnPoints")]
public class SpawnPointDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    public bool IsEnabled { get; set; }
    public int RareNPCChance { get; set; }
    public int LevelMod { get; set; }
    public float SpawnDelay { get; set; }
    public bool Staggerable { get; set; }
    public float StaggerMod { get; set; }
    public bool NightSpawn { get; set; }
    public string? PatrolPoints { get; set; }
    public bool LoopPatrol { get; set; }
    public float RandomWanderRange { get; set; }
    public string? SpawnUponQuestCompleteDBName { get; set; }
    public string? StopIfQuestCompleteDBNames { get; set; }
    public string? ProtectorName { get; set; }
}
