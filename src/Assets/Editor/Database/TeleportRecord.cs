#nullable enable

using SQLite;

[Table("Teleports")]
public class TeleportRecord
{
    public const string TableName = "Teleports";
    
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string TeleportItemStableKey { get; set; } = string.Empty;
}