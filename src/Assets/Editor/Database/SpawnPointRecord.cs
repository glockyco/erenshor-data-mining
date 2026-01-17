#nullable enable

using SQLite;

[Table("SpawnPoints")]
public class SpawnPointRecord
{
    public const string TableName = "SpawnPoints";

    [PrimaryKey]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    public bool IsEnabled { get; set; }
    public int RareNPCChance { get; set; }
    public int LevelMod { get; set; }
    public float SpawnDelay1 { get; set; }
    public float SpawnDelay2 { get; set; }
    public float SpawnDelay3 { get; set; }
    public float SpawnDelay4 { get; set; }
    public bool Staggerable { get; set; }
    public float StaggerMod { get; set; }
    public bool NightSpawn { get; set; }
    public string? PatrolPoints { get; set; }
    public bool LoopPatrol { get; set; }
    public float RandomWanderRange { get; set; }
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string? SpawnUponQuestCompleteStableKey { get; set; }
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string? ProtectorStableKey { get; set; }
}
