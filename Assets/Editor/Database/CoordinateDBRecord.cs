using SQLite;

[Table("Coordinates")]
public class CoordinateDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    
    public string Scene { get; set; }
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }
    
    public string Category { get; set; }
    
    [Indexed]
    public int? AchievementTriggerId { get; set; }
    [Indexed]
    public int? CharacterId { get; set; }
    [Indexed]
    public int? MiningNodeId { get; set; }
    [Indexed]
    public int? SpawnPointId { get; set; }
    [Indexed]
    public int? TreasureLocId { get; set; }
    [Indexed]
    public int? WaterId { get; set; }
    [Indexed]
    public int? ZoneLineId { get; set; }
    
    public enum CoordinateCategory
    {
        AchievementTrigger,
        Character,
        MiningNode,
        SpawnPoint,
        TreasureLoc,
        Water,
        ZoneLine,
    }
}