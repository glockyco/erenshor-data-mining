#nullable enable

using SQLite;

/// <summary>
/// Junction table mapping quests to zones where they are completed.
/// Represents the ZoneAnnounce.CompleteQuestOnEnter and CompleteSecondQuestOnEnter relationships.
/// </summary>
[Table("QuestZoneCompletions")]
public class QuestZoneCompletionRecord
{
    public const string TableName = "QuestZoneCompletions";

    /// <summary>
    /// The DBName of the quest being completed (Quest.DBName).
    /// </summary>
    [Indexed(Name = "QuestZoneCompletions_Primary_IDX", Order = 1, Unique = true)]
    public string QuestDBName { get; set; } = string.Empty;

    /// <summary>
    /// The scene name of the zone that completes the quest (ZoneAnnounce.SceneName).
    /// </summary>
    [Indexed(Name = "QuestZoneCompletions_Primary_IDX", Order = 2, Unique = true)]
    public string ZoneSceneName { get; set; } = string.Empty;
}
