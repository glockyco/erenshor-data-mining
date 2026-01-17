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
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? KeyItemStableKey { get; set; }
}
