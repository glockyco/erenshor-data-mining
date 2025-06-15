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
    
    public int AchievementTriggerId { get; set; }
    public int CharacterId { get; set; }
    public int MiningNodeId { get; set; }
    public int SpawnPointId { get; set; }
    public int TreasureLocId { get; set; }
    public int WaterId { get; set; }
    public int ZoneLineId { get; set; }
    
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