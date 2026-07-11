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

    // Keep rejected geometry candidates in the raw/clean audit table so a new
    // scene update can be reviewed without re-running a different detector.
    public bool IsExcluded { get; set; }
    public string? ExclusionReason { get; set; }

    public enum SecretPassageType
    {
        None,
        HiddenDoor,
        IllusoryWall,
        InvisibleFloor,
    }
}
