#nullable enable

using SQLite;

[Table("SpawnPointTriggers")]
public class SpawnPointTriggerRecord
{
    public const string TableName = "SpawnPointTriggers";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }

    /// <summary>
    /// True if the trigger is active when the scene loads.
    /// False means a scripted event enables it later.
    /// </summary>
    public bool IsEnabledByDefault { get; set; }
}

[Table("SpawnPointTriggerCharacters")]
public class SpawnPointTriggerCharacterRecord
{
    public const string TableName = "SpawnPointTriggerCharacters";

    [Indexed(Name = "SpawnPointTriggerCharacters_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(SpawnPointTriggerRecord), "StableKey")]
    public string SpawnPointTriggerStableKey { get; set; } = string.Empty;

    [Indexed(Name = "SpawnPointTriggerCharacters_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    public float SpawnChance { get; set; }
}
