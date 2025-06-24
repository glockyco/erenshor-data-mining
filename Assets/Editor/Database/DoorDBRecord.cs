#nullable enable

using SQLite;

[Table("Doors")]
public class DoorDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    [Indexed]
    public string? KeyItemId { get; set; }
}