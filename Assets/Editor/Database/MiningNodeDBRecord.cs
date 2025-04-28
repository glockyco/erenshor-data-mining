using SQLite;

[Table("MiningNodes")]
public class MiningNodeDBRecord
{
    [PrimaryKey]
    public string Id { get; set; } // Using scene name + position for unique ID
    public string SceneName { get; set; }
    public float PositionX { get; set; }
    public float PositionY { get; set; }
    public float PositionZ { get; set; }
    public float RespawnTime { get; set; }
}
