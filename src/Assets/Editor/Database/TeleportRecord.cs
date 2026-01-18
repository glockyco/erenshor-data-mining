#nullable enable

using SQLite;

[Table("Teleports")]
public class TeleportRecord
{
    public const string TableName = "Teleports";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string TeleportItemStableKey { get; set; } = string.Empty;
}
