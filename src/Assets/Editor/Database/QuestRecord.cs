#nullable enable

using SQLite;

/// <summary>
/// Canonical quest table - one row per unique DBName.
/// Quest variants with the same DBName share the same completion state at runtime.
/// </summary>
[Table("Quests")]
public class QuestRecord
{
    public const string TableName = "Quests";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty; // Stable identifier: "quest:normalized_dbname"
    public string DBName { get; set; } = string.Empty; // From Quest.DBName (runtime quest identifier)
}
