#nullable enable

using SQLite;

[Table("Doors")]
public class DoorRecord
{
    public const string TableName = "Doors";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }

    [Indexed]
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? KeyItemStableKey { get; set; }
}
