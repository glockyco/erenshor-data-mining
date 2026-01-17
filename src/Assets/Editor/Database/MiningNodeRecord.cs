#nullable enable

using SQLite;

[Table("MiningNodes")]
public class MiningNodeRecord
{
    public const string TableName = "MiningNodes";

    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    public string NPCName { get; set; } = string.Empty;
    public float RespawnTime { get; set; }
}
