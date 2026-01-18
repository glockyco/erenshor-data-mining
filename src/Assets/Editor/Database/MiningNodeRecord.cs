#nullable enable

using SQLite;

[Table("MiningNodes")]
public class MiningNodeRecord
{
    public const string TableName = "MiningNodes";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }

    public string NPCName { get; set; } = string.Empty;
    public float RespawnTime { get; set; }
}
