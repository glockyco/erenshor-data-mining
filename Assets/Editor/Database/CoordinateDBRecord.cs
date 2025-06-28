#nullable enable

using SQLite;

[Table("Coordinates")]
public class CoordinateDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    
    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }

    public string Category { get; set; } = string.Empty;
    
    [Indexed]
    public int? AchievementTriggerId { get; set; }
    [Indexed]
    public int? CharacterId { get; set; }
    [Indexed]
    public int? DoorId { get; set; }
    [Indexed]
    public int? MiningNodeId { get; set; }
    [Indexed]
    public int? SecretPassageId { get; set; }
    [Indexed]
    public int? SpawnPointId { get; set; }
    [Indexed]
    public int? TeleportId { get; set; }
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
        Door,
        MiningNode,
        SecretPassage,
        SpawnPoint,
        Teleport,
        TreasureLoc,
        Water,
        WishingWell,
        ZoneLine,
    }
}