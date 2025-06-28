#nullable enable

using SQLite;

[Table("TreasureHunting")]
public class TreasureHuntingRecord
{
    public const string TableName = "TreasureHunting";
    
    [PrimaryKey]
    public string ZoneName { get; set; } = string.Empty;
    public string ZoneDisplayName { get; set; } = string.Empty;
    public bool IsPickableAlways { get; set; }
    public bool IsPickableGreater20 { get; set; }
    public bool IsPickableGreater30 { get; set; }
}