#nullable enable

using SQLite;

[Table("MiningNodes")]
public class MiningNodeDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    public float RespawnTime { get; set; }
}
