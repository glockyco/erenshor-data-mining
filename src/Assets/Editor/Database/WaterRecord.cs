#nullable enable

using SQLite;

[Table("Waters")]
public class WaterRecord
{
    public const string TableName = "Waters";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }

    public float Width { get; set; }
    public float Height { get; set; }
    public float Depth { get; set; }
}
