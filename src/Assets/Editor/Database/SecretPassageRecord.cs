#nullable enable

using SQLite;

[Table("SecretPassages")]
public class SecretPassageRecord
{
    public const string TableName = "SecretPassages";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }

    public string ObjectName { get; set; } = string.Empty;
    public string Type { get; set; } = string.Empty;

    public enum SecretPassageType
    {
        None,
        HiddenDoor,
        IllusoryWall,
        InvisibleFloor,
    }
}
