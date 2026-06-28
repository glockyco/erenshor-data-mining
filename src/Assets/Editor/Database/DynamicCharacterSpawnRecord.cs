#nullable enable

using SQLite;

[Table("DynamicCharacterSpawns")]
public class DynamicCharacterSpawnRecord
{
    public const string TableName = "DynamicCharacterSpawns";

    [PrimaryKey]
    public string Key { get; set; } = string.Empty;
    public string CharacterStableKey { get; set; } = string.Empty;
    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }
    public string SourceScript { get; set; } = string.Empty;
}
