using SQLite;

[Table("ZoneLines")]
public class ZoneLineRecord
{
    public const string TableName = "ZoneLines";
    
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    public bool IsEnabled { get; set; }
    public string DisplayText { get; set; }
    public string DestinationZone { get; set; }
    public float LandingPositionX { get; set; }
    public float LandingPositionY { get; set; }
    public float LandingPositionZ { get; set; }
    public bool RemoveParty { get; set; }
}