#nullable enable

using SQLite;

[Table("WishingWells")]
public class WishingWellRecord
{
    public const string TableName = "WishingWells";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }
}
