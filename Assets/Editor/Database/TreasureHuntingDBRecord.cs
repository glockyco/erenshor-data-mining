using SQLite;

[Table("TreasureHunting")]
public class TreasureHuntingDBRecord
{
    [PrimaryKey]
    public string ZoneName { get; set; }
    public string ZoneDisplayName { get; set; }
    public bool IsPickableAlways { get; set; }
    public bool IsPickableGreater20 { get; set; }
    public bool IsPickableGreater30 { get; set; }
}