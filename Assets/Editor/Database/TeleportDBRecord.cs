#nullable enable

using SQLite;

[Table("Teleports")]
public class TeleportDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    public string TeleportItemId { get; set; } = string.Empty;
}