#nullable enable

using SQLite;

[Table("AchievementTriggers")]
public class AchievementTriggerRecord
{
    public const string TableName = "AchievementTriggers";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }

    public string AchievementName { get; set; } = string.Empty;
}
