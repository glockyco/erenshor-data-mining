#nullable enable

using SQLite;

[Table("Forges")]
public class ForgeRecord
{
    public const string TableName = "Forges";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }
}
