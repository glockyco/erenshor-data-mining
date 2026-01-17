#nullable enable

using SQLite;

[Table("AchievementTriggers")]
public class AchievementTriggerRecord
{
    public const string TableName = "AchievementTriggers";

    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    public string AchievementName { get; set; } = string.Empty;
}
