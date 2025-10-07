#nullable enable

using SQLite;

[Table("Doors")]
public class DoorRecord
{
    public const string TableName = "Doors";
    
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    [Indexed]
    public string? KeyItemId { get; set; }
}