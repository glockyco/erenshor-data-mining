#nullable enable

using SQLite;

[Table("TreasureLocations")]
public class TreasureLocationRecord
{
    public const string TableName = "TreasureLocations";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }
}
