using SQLite;

[Table("TreasureLocs")]
public class TreasureLocDBRecord
{
    [PrimaryKey]
    public string Id { get; set; }

    public string SceneName { get; set; }
    public float PositionX { get; set; }
    public float PositionY { get; set; }
    public float PositionZ { get; set; }
}